from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from db import models
from ml.knn_common import build_feature_key, parse_compound_header


@dataclass
class ExcelImportSummary:
    filename: str
    total_rows: int = 0
    imported_rows: int = 0
    skipped_rows: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    reference_samples: int = 0
    cleared_existing: bool = False


def _is_empty_cell(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return bool(pd.isna(value))


def _normalize_score(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        score = float(str(value).replace(",", "."))
        if 0 <= score <= 10:
            return round(score, 2)
    except (TypeError, ValueError):
        return None
    return None


def _build_knn_column_map(columns: List[object]) -> Tuple[Dict[str, str], List[str]]:
    column_map: Dict[str, str] = {}
    invalid_columns: List[str] = []
    for col in columns:
        parsed = parse_compound_header(col)
        if not parsed:
            invalid_columns.append(str(col))
            continue
        feature_key = build_feature_key(*parsed)
        if feature_key not in column_map:
            column_map[feature_key] = col
    return column_map, invalid_columns


def import_knn_reference_dataset(
    db: Session,
    *,
    file_bytes: bytes,
    filename: str,
    uploader_id: Optional[int],
) -> ExcelImportSummary:
    summary = ExcelImportSummary(filename=filename)

    try:
        df = pd.read_excel(BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001
        summary.errors.append(f"Không thể đọc file Excel: {exc}")
        return summary

    if df.empty:
        summary.warnings.append("File Excel không có dữ liệu.")
        return summary

    column_map, invalid_columns = _build_knn_column_map(list(df.columns))
    if not column_map:
        summary.errors.append(
            "Không tìm thấy cột điểm hợp lệ (định dạng ví dụ: Toán_1_10, Văn_2_11, Toán_TN)."
        )
        return summary
    if invalid_columns:
        summary.warnings.append(
            f"Các cột không được nhận dạng và sẽ bị bỏ qua: {', '.join(invalid_columns)}"
        )

    existing = db.query(models.KNNReferenceSample).count()
    if existing:
        db.query(models.KNNReferenceSample).delete()
        summary.cleared_existing = True

    for idx, row in df.iterrows():
        row_number = idx + 2
        summary.total_rows += 1
        feature_map: Dict[str, float] = {}

        for feature_key, column_name in column_map.items():
            raw_value = row[column_name]
            if _is_empty_cell(raw_value):
                continue
            score = _normalize_score(raw_value)
            if score is None:
                summary.warnings.append(
                    f"Dòng {row_number}, cột '{column_name}': Điểm không hợp lệ ({raw_value})."
                )
                continue
            feature_map[feature_key] = score

        if not feature_map:
            summary.skipped_rows += 1
            summary.warnings.append(f"Dòng {row_number}: Không có điểm hợp lệ nào, đã bỏ qua.")
            continue

        sample = models.KNNReferenceSample(
            sample_label=f"row_{row_number}",
            feature_data=feature_map,
            metadata_={"column_count": len(feature_map)},
        )
        db.add(sample)
        summary.imported_rows += 1
        summary.reference_samples += 1

    log_metadata = {
        "warnings": summary.warnings,
        "errors": summary.errors,
        "dataset_type": "knn_reference",
        "column_map": list(column_map.keys()),
        "cleared_existing": summary.cleared_existing,
    }
    log_record = models.DataImportLog(
        uploaded_by=uploader_id,
        filename=filename,
        total_rows=summary.total_rows,
        imported_rows=summary.imported_rows,
        skipped_rows=summary.skipped_rows,
        metadata_=log_metadata,
    )
    db.add(log_record)
    db.commit()
    return summary

