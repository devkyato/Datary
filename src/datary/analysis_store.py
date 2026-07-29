"""Disk-backed analysis used to keep recording and inspection memory bounded."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from datary.models import Finding, Record
from datary.utils import temporal_number

_PERCENTILES = (5, 25, 50, 75, 95, 99)


class AnalysisStore:
    """A temporary SQLite spool for exact, bounded-memory analysis."""

    def __init__(self, path: Path, max_fields: int = 1000) -> None:
        self.path = path
        self.max_fields = max_fields
        self.connection = sqlite3.connect(str(path))
        self.connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA temp_store=FILE;
            CREATE TABLE records (
                record_index INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                schema_key TEXT NOT NULL,
                field_count INTEGER NOT NULL
            );
            CREATE TABLE cells (
                record_index INTEGER NOT NULL,
                field TEXT NOT NULL,
                value_kind TEXT NOT NULL,
                text_value TEXT,
                numeric_value REAL,
                PRIMARY KEY (record_index, field)
            );
            CREATE INDEX cells_field_record ON cells(field, record_index);
            CREATE INDEX cells_field_number ON cells(field, numeric_value);
            CREATE TEMP TABLE scratch (position INTEGER, value REAL);
            """
        )
        self._fields: set[str] = set()
        self._count = 0

    def __enter__(self) -> "AnalysisStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def count(self) -> int:
        return self._count

    @property
    def fields(self) -> List[str]:
        return sorted(self._fields)

    def add(self, record: Record) -> None:
        new_fields = set(record) - self._fields
        if len(self._fields | new_fields) > self.max_fields:
            raise ValueError(
                f"dataset exceeds unique field limit ({self.max_fields}); "
                "use a larger --max-fields only for trusted input"
            )
        self._fields.update(new_fields)
        index = self._count
        payload = json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        schema_key = json.dumps(sorted(record), ensure_ascii=False, separators=(",", ":"))
        self.connection.execute(
            "INSERT INTO records VALUES (?, ?, ?, ?)",
            (index, payload, schema_key, len(record)),
        )
        for field, value in record.items():
            kind, text_value, numeric_value = _cell_parts(value)
            self.connection.execute(
                "INSERT INTO cells VALUES (?, ?, ?, ?, ?)",
                (index, field, kind, text_value, numeric_value),
            )
        self._count += 1
        if self._count % 1000 == 0:
            self.connection.commit()

    def finish(self) -> None:
        self.connection.commit()

    def records(self) -> Iterator[Record]:
        cursor = self.connection.execute("SELECT payload FROM records ORDER BY record_index")
        for (payload,) in cursor:
            value = json.loads(str(payload))
            if isinstance(value, dict):
                yield value

    def field_definitions(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for field in self.fields:
            kinds = {
                str(row[0])
                for row in self.connection.execute(
                    "SELECT DISTINCT value_kind FROM cells "
                    "WHERE field = ? AND value_kind != 'null'",
                    (field,),
                )
            }
            if not kinds:
                result[field] = "null"
            elif kinds <= {"int"}:
                result[field] = "integer"
            elif kinds <= {"int", "float"}:
                result[field] = "number"
            elif len(kinds) == 1:
                result[field] = next(iter(kinds))
            else:
                result[field] = "mixed"
        return result

    def metrics(self, time_field: Optional[str] = None) -> Dict[str, Any]:
        numeric: Dict[str, Any] = {}
        for field in self.fields:
            summary = self._numeric_summary(field)
            if summary["valid_count"]:
                numeric[field] = summary
        timing = self._timing_metrics(time_field) if time_field in self._fields else {}
        return {"numeric": numeric, "timing": timing}

    def quality(
        self,
        time_field: Optional[str] = None,
        sequence_field: Optional[str] = None,
        monotonic_fields: Optional[Sequence[str]] = None,
        counter_fields: Optional[Sequence[str]] = None,
    ) -> List[Finding]:
        if not self._count:
            return [
                _finding(
                    "empty-data",
                    "warning",
                    None,
                    "all",
                    0,
                    "> 0 records",
                    "No valid records were parsed.",
                )
            ]
        findings: List[Finding] = []
        duplicate_row = self.connection.execute(
            "SELECT COALESCE(SUM(amount - 1), 0) FROM "
            "(SELECT COUNT(*) AS amount FROM records GROUP BY payload HAVING amount > 1)"
        ).fetchone()
        duplicates = int(duplicate_row[0]) if duplicate_row else 0
        if duplicates:
            findings.append(
                _finding(
                    "duplicate-rows",
                    "warning",
                    None,
                    "multiple",
                    duplicates,
                    0,
                    "Identical records recur.",
                )
            )
        schemas = [
            json.loads(str(row[0]))
            for row in self.connection.execute(
                "SELECT DISTINCT schema_key FROM records ORDER BY schema_key"
            )
        ]
        if len(schemas) > 1:
            findings.append(
                _finding(
                    "record-shape-change",
                    "warning",
                    None,
                    "multiple",
                    schemas,
                    "one stable field set",
                    "Record field names change across the dataset.",
                )
            )
        lengths = [
            int(row[0])
            for row in self.connection.execute(
                "SELECT DISTINCT field_count FROM records ORDER BY field_count"
            )
        ]
        if len(lengths) > 1:
            findings.append(
                _finding(
                    "record-length-change",
                    "warning",
                    None,
                    "multiple",
                    lengths,
                    1,
                    "Record field counts vary.",
                )
            )
        monotonic = set(monotonic_fields or ())
        counters = set(counter_fields or ())
        for field in self.fields:
            findings.extend(
                self._field_quality(
                    field,
                    field in monotonic,
                    field in counters,
                    field in {time_field, sequence_field},
                )
            )
        if time_field and time_field in self._fields:
            findings.extend(self._timing_quality(time_field))
        if sequence_field and sequence_field in self._fields:
            findings.extend(self._sequence_quality(sequence_field))
        return sorted(findings, key=lambda item: (item.check_id, item.field or "", item.affected))

    def control_metrics(
        self,
        time_field: str,
        target_field: str,
        response_field: str,
    ) -> Dict[str, Any]:
        """Calculate step-response metrics in bounded memory."""

        initial_response: Optional[float] = None
        final_target: Optional[float] = None
        target_min = math.inf
        target_max = -math.inf
        valid_count = 0
        for record in self.records():
            time_value = temporal_number(record.get(time_field))
            target = _finite(record.get(target_field))
            response = _finite(record.get(response_field))
            if time_value is None or target is None or response is None:
                continue
            if initial_response is None:
                initial_response = response
            final_target = target
            target_min = min(target_min, target)
            target_max = max(target_max, target)
            valid_count += 1
        if valid_count < 2 or initial_response is None or final_target is None:
            return {}
        span = final_target - initial_response
        stable_target = target_max - target_min <= max(abs(final_target), 1.0) * 1e-9
        tolerance = max(abs(span), abs(final_target), 1e-12) * 0.02
        rise_10: Optional[float] = None
        rise_90: Optional[float] = None
        peak: Optional[float] = None
        first_time: Optional[float] = None
        settling_candidate: Optional[float] = None
        previous_time: Optional[float] = None
        previous_error: Optional[float] = None
        absolute_error_sum = 0.0
        squared_error_sum = 0.0
        integral_absolute = 0.0
        integral_squared = 0.0
        final_error = 0.0
        backwards = 0
        for record in self.records():
            time_value = temporal_number(record.get(time_field))
            target = _finite(record.get(target_field))
            response = _finite(record.get(response_field))
            if time_value is None or target is None or response is None:
                continue
            if first_time is None:
                first_time = time_value
            error = target - response
            final_error = error
            absolute_error_sum += abs(error)
            squared_error_sum += error * error
            peak = (
                response
                if peak is None
                else (max(peak, response) if span >= 0 else min(peak, response))
            )
            if stable_target:
                if rise_10 is None and _crossed(response, initial_response + span * 0.1, span):
                    rise_10 = time_value
                if rise_90 is None and _crossed(response, initial_response + span * 0.9, span):
                    rise_90 = time_value
                if abs(response - final_target) <= tolerance:
                    if settling_candidate is None:
                        settling_candidate = time_value
                else:
                    settling_candidate = None
            if previous_time is not None and previous_error is not None:
                delta_time = time_value - previous_time
                if delta_time >= 0:
                    integral_absolute += delta_time * (abs(previous_error) + abs(error)) / 2
                    integral_squared += (
                        delta_time * (previous_error * previous_error + error * error) / 2
                    )
                else:
                    backwards += 1
            previous_time = time_value
            previous_error = error
        assert peak is not None
        overshoot: Optional[float]
        if span and stable_target:
            overshoot = (
                (peak - final_target) / abs(span) * 100
                if span >= 0
                else (final_target - peak) / abs(span) * 100
            )
        else:
            overshoot = None
        warnings: List[str] = []
        if not stable_target:
            warnings.append(
                "The target changes during the record; step-response metrics are not reported."
            )
        if backwards:
            warnings.append(
                f"{backwards} backwards time interval(s) were excluded from integration."
            )
        return {
            "rise_time": (
                rise_90 - rise_10 if rise_10 is not None and rise_90 is not None else None
            ),
            "peak_value": peak,
            "percentage_overshoot": overshoot,
            "settling_time": (
                settling_candidate - first_time
                if settling_candidate is not None and first_time is not None
                else None
            ),
            "steady_state_error": final_error,
            "mean_absolute_error": absolute_error_sum / valid_count,
            "root_mean_squared_error": math.sqrt(squared_error_sum / valid_count),
            "integral_absolute_error": integral_absolute,
            "integral_squared_error": integral_squared,
            "required_fields": {
                "time": time_field,
                "target": target_field,
                "response": response_field,
            },
            "assumptions": [
                "Rise time, overshoot, and settling time require a stable step target.",
                "Rise-time crossings use recorded samples without interpolation.",
                "Settling uses a ±2% band based on the larger of step span or target magnitude.",
                "Error integrals use trapezoidal integration over non-decreasing timestamps.",
            ],
            "warnings": warnings,
        }

    def network_metrics(
        self,
        sequence_field: str,
        latency_field: str,
        bytes_field: Optional[str] = None,
        time_field: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.connection.execute("DELETE FROM scratch")
        sequence_count = 0
        sequence_min: Optional[int] = None
        sequence_max: Optional[int] = None
        previous: Optional[int] = None
        out_of_order = 0
        invalid_sequences = 0
        sequence_batch: List[Tuple[int, float]] = []
        for index, value in self._numeric_rows(sequence_field):
            if not value.is_integer():
                invalid_sequences += 1
                continue
            sequence = int(value)
            sequence_count += 1
            sequence_batch.append((index, float(sequence)))
            if len(sequence_batch) >= 1000:
                self.connection.executemany(
                    "INSERT INTO scratch(position, value) VALUES (?, ?)",
                    sequence_batch,
                )
                sequence_batch.clear()
            sequence_min = sequence if sequence_min is None else min(sequence_min, sequence)
            sequence_max = sequence if sequence_max is None else max(sequence_max, sequence)
            if previous is not None and sequence < previous:
                out_of_order += 1
            previous = sequence
        if sequence_batch:
            self.connection.executemany(
                "INSERT INTO scratch(position, value) VALUES (?, ?)",
                sequence_batch,
            )
        distinct_row = self.connection.execute(
            "SELECT COUNT(DISTINCT value) FROM scratch"
        ).fetchone()
        distinct = int(distinct_row[0]) if distinct_row else 0
        expected = (
            sequence_max - sequence_min + 1
            if sequence_min is not None and sequence_max is not None
            else 0
        )
        self.connection.execute("DELETE FROM scratch")
        latency_count = 0
        latency_mean = 0.0
        previous_latency: Optional[float] = None
        latency_difference_total = 0.0
        latency_difference_count = 0
        negative_latencies = 0
        latency_batch: List[Tuple[int, float]] = []
        for index, value in self._numeric_rows(latency_field):
            if value < 0:
                negative_latencies += 1
                continue
            latency_count += 1
            latency_mean += (value - latency_mean) / latency_count
            if previous_latency is not None:
                latency_difference_total += abs(value - previous_latency)
                latency_difference_count += 1
            previous_latency = value
            latency_batch.append((index, value))
            if len(latency_batch) >= 1000:
                self.connection.executemany(
                    "INSERT INTO scratch(position, value) VALUES (?, ?)",
                    latency_batch,
                )
                latency_batch.clear()
        if latency_batch:
            self.connection.executemany(
                "INSERT INTO scratch(position, value) VALUES (?, ?)",
                latency_batch,
            )
        median_latency = self._scratch_percentile(latency_count, 50) if latency_count else None
        percentile_latency = (
            {
                str(percentile): self._scratch_percentile(latency_count, percentile)
                for percentile in _PERCENTILES
            }
            if latency_count
            else {}
        )
        warnings = [
            warning
            for warning in (
                (
                    f"{invalid_sequences} non-integer sequence value(s) were excluded."
                    if invalid_sequences
                    else ""
                ),
                (
                    f"{negative_latencies} negative latency value(s) were excluded."
                    if negative_latencies
                    else ""
                ),
            )
            if warning
        ]
        result: Dict[str, Any] = {
            "packet_loss_estimate": ((expected - distinct) / expected if expected else None),
            "duplicate_packet_rate": (
                (sequence_count - distinct) / sequence_count if sequence_count else None
            ),
            "out_of_order_count": out_of_order,
            "mean_latency": latency_mean if latency_count else None,
            "median_latency": median_latency,
            "latency_jitter": (
                latency_difference_total / latency_difference_count
                if latency_difference_count
                else 0.0
            ),
            "percentile_latency": percentile_latency,
            "required_fields": {
                "sequence": sequence_field,
                "latency": latency_field,
                "bytes": bytes_field,
                "time": time_field,
            },
            "assumptions": [
                "Sequence identifiers are expected to be contiguous integers.",
                "Latency jitter is the mean absolute difference between consecutive valid samples.",
            ],
            "warnings": warnings,
        }
        if bytes_field:
            total_bytes = 0.0
            negative_bytes = 0
            for _, value in self._numeric_rows(bytes_field):
                if value < 0:
                    negative_bytes += 1
                else:
                    total_bytes += value
            if negative_bytes:
                warnings.append(f"{negative_bytes} negative byte count(s) were excluded.")
            result["total_bytes"] = total_bytes
            if time_field:
                first_time: Optional[float] = None
                last_time: Optional[float] = None
                for _, value in self._time_rows(time_field):
                    if first_time is None:
                        first_time = value
                    last_time = value
                duration = (
                    last_time - first_time
                    if first_time is not None and last_time is not None
                    else 0.0
                )
                result["throughput_bytes_per_second"] = (
                    float(total_bytes) / duration
                    if total_bytes is not None and duration > 0
                    else None
                )
        return result

    def close(self) -> None:
        self.connection.close()

    def _numeric_summary(self, field: str) -> Dict[str, Any]:
        values = self._numeric_rows(field)
        count = 0
        mean = 0.0
        m2 = 0.0
        total = 0.0
        total_compensation = 0.0
        square_total = 0.0
        square_compensation = 0.0
        first: Optional[float] = None
        last: Optional[float] = None
        previous: Optional[float] = None
        difference_total = 0.0
        difference_compensation = 0.0
        difference_count = 0
        for _, value in values:
            count += 1
            if first is None:
                first = value
            last = value
            delta = value - mean
            mean += delta / count
            m2 += delta * (value - mean)
            total, total_compensation = _compensated_add(total, total_compensation, value)
            square_total, square_compensation = _compensated_add(
                square_total, square_compensation, value * value
            )
            if previous is not None:
                difference_total, difference_compensation = _compensated_add(
                    difference_total,
                    difference_compensation,
                    abs(value - previous),
                )
                difference_count += 1
            previous = value
        if not count:
            return {
                "count": self._count,
                "valid_count": 0,
                "missing_count": self._count,
            }
        minimum, maximum = self.connection.execute(
            "SELECT MIN(numeric_value), MAX(numeric_value) FROM cells "
            "WHERE field = ? AND numeric_value IS NOT NULL",
            (field,),
        ).fetchone()
        return {
            "count": self._count,
            "valid_count": count,
            "missing_count": self._count - count,
            "minimum": float(minimum),
            "maximum": float(maximum),
            "mean": mean,
            "median": self._percentile(field, count, 50),
            "standard_deviation": math.sqrt(m2 / (count - 1)) if count > 1 else 0.0,
            "variance": m2 / (count - 1) if count > 1 else 0.0,
            "percentiles": {
                str(percentile): self._percentile(field, count, percentile)
                for percentile in _PERCENTILES
            },
            "sum": total + total_compensation,
            "rate_of_change": (last - first) if first is not None and last is not None else 0.0,
            "root_mean_square": math.sqrt((square_total + square_compensation) / count),
            "mean_absolute_difference": (
                (difference_total + difference_compensation) / difference_count
                if difference_count
                else 0.0
            ),
            "sparkline_values": self._ordered_samples(field, count, 40),
        }

    def _percentile(self, field: str, count: int, percentile: int) -> float:
        index = (count - 1) * percentile / 100
        low = math.floor(index)
        high = math.ceil(index)
        low_value = self._ordered_value(field, low)
        if low == high:
            return low_value
        high_value = self._ordered_value(field, high)
        return low_value * (high - index) + high_value * (index - low)

    def _ordered_value(self, field: str, offset: int) -> float:
        row = self.connection.execute(
            "SELECT numeric_value FROM cells "
            "WHERE field = ? AND numeric_value IS NOT NULL "
            "ORDER BY numeric_value LIMIT 1 OFFSET ?",
            (field, offset),
        ).fetchone()
        if row is None:
            raise ValueError("numeric percentile requested for empty field")
        return float(row[0])

    def _ordered_samples(self, field: str, count: int, maximum: int) -> List[float]:
        sample_count = min(count, maximum)
        offsets = (
            [0]
            if sample_count == 1
            else [round(index * (count - 1) / (sample_count - 1)) for index in range(sample_count)]
        )
        values: List[float] = []
        for offset in offsets:
            row = self.connection.execute(
                "SELECT numeric_value FROM cells "
                "WHERE field = ? AND numeric_value IS NOT NULL "
                "ORDER BY record_index LIMIT 1 OFFSET ?",
                (field, offset),
            ).fetchone()
            if row is not None:
                values.append(float(row[0]))
        return values

    def _numeric_rows(self, field: str) -> Iterator[Tuple[int, float]]:
        cursor = self.connection.execute(
            "SELECT record_index, numeric_value FROM cells "
            "WHERE field = ? AND numeric_value IS NOT NULL ORDER BY record_index",
            (field,),
        )
        for record_index, value in cursor:
            yield int(record_index), float(value)

    def _timing_metrics(self, field: str) -> Dict[str, Any]:
        self.connection.execute("DELETE FROM scratch")
        self.connection.executemany(
            "INSERT INTO scratch(position, value) VALUES (?, ?)",
            self._time_rows(field),
        )
        time_counts = self.connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT value) FROM scratch"
        ).fetchone()
        duplicate_count = int(time_counts[0]) - int(time_counts[1])
        self.connection.execute("DELETE FROM scratch")
        interval_count = 0
        positive_count = 0
        positive_mean = 0.0
        positive_m2 = 0.0
        minimum = math.inf
        maximum = -math.inf
        backward_count = 0
        batch: List[Tuple[int, float]] = []
        for index, interval in self._intervals(field):
            interval_count += 1
            minimum = min(minimum, interval)
            maximum = max(maximum, interval)
            if interval > 0:
                positive_count += 1
                delta = interval - positive_mean
                positive_mean += delta / positive_count
                positive_m2 += delta * (interval - positive_mean)
                batch.append((index, interval))
                if len(batch) >= 1000:
                    self.connection.executemany(
                        "INSERT INTO scratch(position, value) VALUES (?, ?)", batch
                    )
                    batch.clear()
            elif interval < 0:
                backward_count += 1
        if batch:
            self.connection.executemany("INSERT INTO scratch(position, value) VALUES (?, ?)", batch)
        start: Optional[float] = None
        end: Optional[float] = None
        for _, value in self._time_rows(field):
            if start is None:
                start = value
            end = value
        if start is None or end is None:
            return {}
        if not interval_count:
            return {
                "start": start,
                "end": end,
                "duration": 0.0,
                "mean_interval": None,
                "median_interval": None,
                "minimum_interval": None,
                "maximum_interval": None,
                "jitter": 0.0,
                "effective_sample_rate": None,
                "gap_count": 0,
                "duplicate_timestamp_count": 0,
                "backward_timestamp_count": 0,
            }
        median = self._scratch_percentile(positive_count, 50)
        return {
            "start": start,
            "end": end,
            "duration": end - start,
            "mean_interval": positive_mean,
            "median_interval": median,
            "minimum_interval": minimum,
            "maximum_interval": maximum,
            "jitter": (math.sqrt(positive_m2 / positive_count) if positive_count > 1 else 0.0),
            "effective_sample_rate": (1.0 / positive_mean if positive_mean > 0 else None),
            "gap_count": (
                int(
                    self.connection.execute(
                        "SELECT COUNT(*) FROM scratch WHERE value >= ?",
                        (median * 2,),
                    ).fetchone()[0]
                )
                if median > 0
                else 0
            ),
            "duplicate_timestamp_count": duplicate_count,
            "backward_timestamp_count": backward_count,
        }

    def _field_quality(
        self,
        field: str,
        monotonic: bool,
        counter: bool,
        is_time: bool,
    ) -> List[Finding]:
        findings: List[Finding] = []
        missing = _Affected()
        cursor = self.connection.execute(
            "SELECT records.record_index, cells.value_kind, cells.text_value "
            "FROM records LEFT JOIN cells ON records.record_index = cells.record_index "
            "AND cells.field = ? ORDER BY records.record_index",
            (field,),
        )
        for index, kind, text_value in cursor:
            if kind is None or kind == "null" or (kind == "str" and text_value == ""):
                missing.add(int(index))
        if missing.count:
            findings.append(
                _finding(
                    "missing-values",
                    "warning",
                    field,
                    missing.range,
                    missing.count,
                    0,
                    "Values are absent.",
                )
            )
        kinds = {
            str(row[0])
            for row in self.connection.execute(
                "SELECT DISTINCT value_kind FROM cells WHERE field = ? AND value_kind != 'null'",
                (field,),
            )
        }
        if len(kinds) > 1 and not kinds <= {"int", "float"}:
            findings.append(
                _finding(
                    "type-change",
                    "warning",
                    field,
                    "multiple",
                    sorted(kinds),
                    1,
                    "The field changes type.",
                )
            )
        unsafe_integer_row = self.connection.execute(
            "SELECT COUNT(*), MIN(record_index), MAX(record_index) FROM cells "
            "WHERE field = ? AND value_kind = 'int' AND numeric_value IS NULL",
            (field,),
        ).fetchone()
        unsafe_integer_count = int(unsafe_integer_row[0])
        if unsafe_integer_count:
            first = int(unsafe_integer_row[1])
            last = int(unsafe_integer_row[2])
            findings.append(
                _finding(
                    "invalid-values",
                    "warning",
                    field,
                    str(first) if first == last else f"{first}-{last}",
                    unsafe_integer_count,
                    "integer magnitude ≤ 2^53 for exact binary64 analysis",
                    "Large integers were preserved but excluded from numeric analysis.",
                )
            )
        if is_time:
            return findings
        rows = self._numeric_rows(field)
        first_row: Optional[Tuple[int, float]] = None
        previous: Optional[Tuple[int, float]] = None
        minimum = math.inf
        maximum = -math.inf
        count = 0
        decreases = _Affected()
        best_start = best_end = current_start = 0
        best_length = current_length = 0
        for index, value in rows:
            count += 1
            if first_row is None:
                first_row = (index, value)
                current_start = index
                current_length = 1
            elif previous is not None:
                if value < previous[1]:
                    decreases.add(index)
                if value == previous[1] and index == previous[0] + 1:
                    current_length += 1
                else:
                    current_start = index
                    current_length = 1
            if current_length > best_length:
                best_start, best_end, best_length = current_start, index, current_length
            minimum = min(minimum, value)
            maximum = max(maximum, value)
            previous = (index, value)
        if monotonic and decreases.count:
            findings.append(
                _finding(
                    "monotonicity-violation",
                    "warning",
                    field,
                    decreases.range,
                    decreases.count,
                    "no decreases",
                    "The field decreases despite an explicit monotonicity expectation.",
                    ["Missing values are ignored between consecutive valid values."],
                    "Confirm ordering and whether resets or wraparound are expected.",
                )
            )
        if counter and decreases.count:
            findings.append(
                _finding(
                    "counter-reset",
                    "warning",
                    field,
                    decreases.range,
                    decreases.count,
                    "no decreases",
                    "The counter decreases, indicating a reset, rollover, or reordered record.",
                    ["The selected field is expected to be a non-decreasing counter."],
                    "Check device restarts, counter width, wraparound, and record ordering.",
                )
            )
        if count >= 2 and minimum == maximum and first_row and previous:
            findings.append(
                _finding(
                    "constant-signal",
                    "info",
                    field,
                    f"{first_row[0]}-{previous[0]}",
                    minimum,
                    "no variation",
                    "The signal is constant.",
                )
            )
        if best_length >= 5 and best_length < count:
            findings.append(
                _finding(
                    "frozen-values",
                    "warning",
                    field,
                    f"{best_start}-{best_end}",
                    best_length,
                    5,
                    "The same value repeats for an extended run.",
                    ["Missing values break a frozen run."],
                )
            )
        if count >= 5:
            findings.extend(self._distribution_quality(field, count))
        return findings

    def _distribution_quality(self, field: str, count: int) -> List[Finding]:
        findings: List[Finding] = []
        median = self._percentile(field, count, 50)
        self.connection.execute("DELETE FROM scratch")
        self.connection.executemany(
            "INSERT INTO scratch(position, value) VALUES (?, ?)",
            ((index, abs(value - median)) for index, value in self._numeric_rows(field)),
        )
        deviation_count = int(self.connection.execute("SELECT COUNT(*) FROM scratch").fetchone()[0])
        mad = self._scratch_percentile(deviation_count, 50)
        outliers = _Affected()
        for index, value in self._numeric_rows(field):
            if abs(value - median) > 6 * mad if mad > 0 else value != median:
                outliers.add(index)
        if outliers.count:
            threshold = "6 × MAD" if mad > 0 else "different from zero-MAD median"
            findings.append(
                _finding(
                    "outliers",
                    "warning",
                    field,
                    outliers.range,
                    outliers.count,
                    threshold,
                    "Values are far from the median.",
                    ["Robust median absolute deviation rule."],
                )
            )
        self.connection.execute("DELETE FROM scratch")
        previous: Optional[float] = None
        differences: List[Tuple[int, float]] = []
        for index, value in self._numeric_rows(field):
            if previous is not None:
                differences.append((index, abs(value - previous)))
            previous = value
            if len(differences) >= 1000:
                self.connection.executemany(
                    "INSERT INTO scratch(position, value) VALUES (?, ?)",
                    differences,
                )
                differences.clear()
        if differences:
            self.connection.executemany(
                "INSERT INTO scratch(position, value) VALUES (?, ?)",
                differences,
            )
        difference_count = int(
            self.connection.execute("SELECT COUNT(*) FROM scratch").fetchone()[0]
        )
        base = self._scratch_percentile(difference_count, 50)
        spikes = _Affected()
        for index, value in self.connection.execute(
            "SELECT position, value FROM scratch ORDER BY position"
        ):
            if value > base * 10 if base > 0 else value > 0:
                spikes.add(int(index))
        if spikes.count:
            threshold = (
                "10 × median absolute step" if base > 0 else "non-zero step after zero baseline"
            )
            findings.append(
                _finding(
                    "sudden-spikes",
                    "warning",
                    field,
                    spikes.range,
                    spikes.count,
                    threshold,
                    "Abrupt changes exceed the configured robust threshold.",
                )
            )
        summary = self._numeric_summary(field)
        mean = float(summary["mean"])
        deviation = float(summary["standard_deviation"])
        if mean and deviation / abs(mean) > 0.5:
            findings.append(
                _finding(
                    "high-noise",
                    "info",
                    field,
                    "all",
                    deviation,
                    "coefficient of variation > 0.5",
                    "Variation is high relative to the mean.",
                    ["Only meaningful for ratio-scale signals."],
                )
            )
        return findings

    def _scratch_percentile(self, count: int, percentile: int) -> float:
        if not count:
            return 0.0
        index = (count - 1) * percentile / 100
        low = math.floor(index)
        high = math.ceil(index)
        low_value = float(
            self.connection.execute(
                "SELECT value FROM scratch ORDER BY value LIMIT 1 OFFSET ?",
                (low,),
            ).fetchone()[0]
        )
        if low == high:
            return low_value
        high_value = float(
            self.connection.execute(
                "SELECT value FROM scratch ORDER BY value LIMIT 1 OFFSET ?",
                (high,),
            ).fetchone()[0]
        )
        return low_value * (high - index) + high_value * (index - low)

    def _intervals(self, field: str) -> Iterator[Tuple[int, float]]:
        previous: Optional[float] = None
        for index, value in self._time_rows(field):
            if previous is not None:
                yield index, value - previous
            previous = value

    def _time_rows(self, field: str) -> Iterator[Tuple[int, float]]:
        cursor = self.connection.execute(
            "SELECT record_index, value_kind, text_value, numeric_value FROM cells "
            "WHERE field = ? ORDER BY record_index",
            (field,),
        )
        for record_index, kind, text_value, numeric_value in cursor:
            raw: Any = numeric_value if kind in {"int", "float"} else text_value
            value = temporal_number(raw)
            if value is not None:
                yield int(record_index), value

    def _timing_quality(self, field: str) -> List[Finding]:
        findings: List[Finding] = []
        duplicate = _Affected()
        backward = _Affected()
        self.connection.execute("DELETE FROM scratch")
        self.connection.executemany(
            "INSERT INTO scratch(position, value) VALUES (?, ?)",
            self._time_rows(field),
        )
        for (index,) in self.connection.execute(
            "SELECT position FROM scratch WHERE position NOT IN "
            "(SELECT MIN(position) FROM scratch GROUP BY value) ORDER BY position"
        ):
            duplicate.add(int(index))
        self.connection.execute("DELETE FROM scratch")
        batch: List[Tuple[int, float]] = []
        for index, interval in self._intervals(field):
            if interval < 0:
                backward.add(index)
            elif interval > 0:
                batch.append((index, interval))
                if len(batch) >= 1000:
                    self.connection.executemany(
                        "INSERT INTO scratch(position, value) VALUES (?, ?)", batch
                    )
                    batch.clear()
        if batch:
            self.connection.executemany("INSERT INTO scratch(position, value) VALUES (?, ?)", batch)
        if duplicate.count:
            findings.append(
                _finding(
                    "duplicate-timestamps",
                    "warning",
                    field,
                    duplicate.range,
                    duplicate.count,
                    0,
                    "Adjacent timestamps are equal.",
                )
            )
        if backward.count:
            findings.append(
                _finding(
                    "timestamps-backwards",
                    "error",
                    field,
                    backward.range,
                    backward.count,
                    0,
                    "Time moves backwards.",
                )
            )
        positive_count = int(self.connection.execute("SELECT COUNT(*) FROM scratch").fetchone()[0])
        if positive_count > 2:
            median = self._scratch_percentile(positive_count, 50)
            irregular = _Affected()
            gaps = _Affected()
            for index, interval in self.connection.execute(
                "SELECT position, value FROM scratch ORDER BY position"
            ):
                if abs(float(interval) - median) > median * 0.2:
                    irregular.add(int(index))
                if float(interval) > median * 2:
                    gaps.add(int(index))
            if irregular.count:
                findings.append(
                    _finding(
                        "irregular-timing",
                        "warning",
                        field,
                        irregular.range,
                        irregular.count,
                        "±20% of median interval",
                        "Sampling intervals vary.",
                    )
                )
            if gaps.count:
                findings.append(
                    _finding(
                        "large-timing-gaps",
                        "warning",
                        field,
                        gaps.range,
                        gaps.count,
                        "2 × median interval",
                        "Large gaps occur in sampling.",
                    )
                )
        return findings

    def _sequence_quality(self, field: str) -> List[Finding]:
        self.connection.execute("DELETE FROM scratch")
        invalid = _Affected()
        batch: List[Tuple[int, float]] = []
        for index, value in self._numeric_rows(field):
            if not value.is_integer():
                invalid.add(index)
                continue
            batch.append((index, value))
            if len(batch) >= 1000:
                self.connection.executemany(
                    "INSERT INTO scratch(position, value) VALUES (?, ?)", batch
                )
                batch.clear()
        if batch:
            self.connection.executemany("INSERT INTO scratch(position, value) VALUES (?, ?)", batch)
        findings: List[Finding] = []
        if invalid.count:
            findings.append(
                _finding(
                    "invalid-values",
                    "warning",
                    field,
                    invalid.range,
                    invalid.count,
                    "integer sequence identifiers",
                    "Sequence identifiers contain non-integer numeric values.",
                )
            )
        row = self.connection.execute(
            "SELECT MIN(value), MAX(value), COUNT(DISTINCT value) FROM scratch"
        ).fetchone()
        if row is None or row[0] is None:
            return findings
        expected = int(float(row[1])) - int(float(row[0])) + 1
        lost = expected - int(row[2])
        if lost <= 0:
            return findings
        findings.append(
            _finding(
                "packet-loss",
                "warning",
                field,
                "range",
                lost,
                0,
                "Sequence identifiers contain gaps.",
                ["Identifiers are expected to increase by one."],
            )
        )
        return findings


class _Affected:
    def __init__(self) -> None:
        self.count = 0
        self.first: Optional[int] = None
        self.last: Optional[int] = None

    def add(self, index: int) -> None:
        if self.first is None:
            self.first = index
        self.last = index
        self.count += 1

    @property
    def range(self) -> str:
        if self.first is None or self.last is None:
            return ""
        return str(self.first) if self.first == self.last else f"{self.first}-{self.last}"


def _cell_parts(value: Any) -> Tuple[str, Optional[str], Optional[float]]:
    if value is None:
        return "null", None, None
    if isinstance(value, bool):
        return "bool", "true" if value else "false", None
    if isinstance(value, int):
        numeric = float(value) if abs(value) <= 2**53 else None
        return "int", str(value), numeric
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numbers cannot be analysed")
        return "float", repr(value), value
    if isinstance(value, str):
        return "str", value, None
    if isinstance(value, list):
        return "list", json.dumps(value, ensure_ascii=False, sort_keys=True), None
    if isinstance(value, dict):
        return "dict", json.dumps(value, ensure_ascii=False, sort_keys=True), None
    raise ValueError(f"unsupported record value: {type(value).__name__}")


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _crossed(value: float, level: float, direction: float) -> bool:
    return value >= level if direction >= 0 else value <= level


def _compensated_add(total: float, compensation: float, value: float) -> Tuple[float, float]:
    updated = total + value
    if abs(total) >= abs(value):
        compensation += (total - updated) + value
    else:
        compensation += (value - updated) + total
    return updated, compensation


def _finding(
    check_id: str,
    severity: str,
    field: Optional[str],
    affected: str,
    evidence: Any,
    threshold: Any,
    explanation: str,
    assumptions: Optional[List[str]] = None,
    suggestion: str = "Inspect the affected raw records and confirm domain expectations.",
) -> Finding:
    return Finding(
        check_id,
        severity,
        field,
        affected,
        evidence,
        threshold,
        explanation,
        assumptions or [],
        suggestion,
    )
