
from datetime import datetime
from typing import Any, Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import Column, Engine, Table, create_engine, select

from oncall_bot.config import load_config
from oncall_bot.tables import OncallInfo, get_tracking_table


class Storage(object):

    def __init__(self, engine: Engine):
        self.engine = engine

    def create_table(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(OncallInfo.create())

    def query_table(self, table: Table, row_id: Any, columns: List[Column]) -> Optional[dict]:
        primary_key_column = [key.name for key in table.primary_key][0]

        with self.engine.connect() as conn:
            print(f"Querying table {table.name} with row_id {row_id} with columns {columns}")
            stmt = select(*columns).where(table.c[primary_key_column] == row_id)
            result = conn.execute(stmt)
            if result.rowcount == 0:
                return None
            return result.fetchone()._asdict()

    def upsert_table(self, table: Table, row_id: Any, data: Dict[str, Any]) -> None:
        primary_key_column = [key.name for key in table.primary_key][0]

        with self.engine.connect() as conn:
            select_stmt = table.select().where(table.c[primary_key_column] == row_id)
            row_exists = conn.execute(select_stmt).fetchone()

            # Step 2: Update or Insert based on existence
            if row_exists:
                update_stmt = table.update().where(table.c[primary_key_column] == row_id).values(data)
                conn.execute(update_stmt)
                print("Row updated")
            else:
                data[primary_key_column] = row_id
                insert_stmt = table.insert().values(**data)
                conn.execute(insert_stmt)
                print("Row inserted")

    def get_summary(self, tracking_url: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        tracking_table = get_tracking_table(tracking_url)
        with self.engine.connect() as conn:
            stmt = select("*").where(
                tracking_table.c.requested_at >= start_time,
                tracking_table.c.requested_at <= end_time
            )
            result = [row._asdict() for row in conn.execute(stmt).fetchall()]


        summary = {}
        summary["total_requests"] = len(result)
        summary["total_PR_reuqests"] = len([r for r in result if r["subject"] == "Code Review"])
        summary["total_support_reuqests"] = len([r for r in result if r["subject"] != "Code Review"])
        summary["unresolved_requests"] = [r for r in result if r["completed_at"] is None]
        return summary


class GSheetStorage(Storage):

    def __init__(self, engine):
        super().__init__(engine)

    def create_table(self, table: Table):
        # shillelagh doesn't support creating tables, therefore we need to use google sheet api to create it
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(
            load_config().google_sheet_service_account,
            scopes=scope
        )
        client = gspread.authorize(creds)

        # Create a new sheet
        spreadsheet = client.create(table.name)

        # Open the first sheet
        worksheet = spreadsheet.sheet1
        worksheet.append_row([
            column.name for column in table.columns
        ])


GoogleSheetObject = None

def get_gsheet_storage() -> GSheetStorage:
    global GoogleSheetObject
    if GoogleSheetObject is None:
        service_account_info = load_config().google_sheet_service_account
        engine = create_engine(
            "gsheets://",
            service_account_info=service_account_info,
            catalog={
                "oncall_info": load_config().google_sheet_root_db
            }
        )
        GoogleSheetObject = GSheetStorage(engine)
    return GoogleSheetObject
