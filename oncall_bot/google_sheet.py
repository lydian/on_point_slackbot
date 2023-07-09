
from typing import Dict, List, Optional, Tuple

import gspread
from google.oauth2.service_account import Credentials

from oncall_bot.config import load_config


class GoogleSheet:

    @staticmethod
    def from_url(url: str, sheet: str = 'sheet1') -> 'GoogleSheet':
        gs = GoogleSheet()
        gs.sheet = getattr(gs.client.open_by_url(url), sheet)
        return gs

    @staticmethod
    def from_file_name(name: str, sheet: str = 'sheet1') -> 'GoogleSheet':
        gs = GoogleSheet()
        gs.sheet = getattr(gs.client.open(name), sheet)
        return gs

    @staticmethod
    def from_oncall_settings() -> 'GoogleSheet':
        return GoogleSheet.from_file_name('oncall_bot_tracking', 'sheet1')

    def __init__(self) -> None:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(load_config().google_sheet_service_account, scopes=scope)
        self.client = gspread.authorize(creds)

    def update_values(self) -> List[List[str]]:
        self.values = self.sheet.get_all_values()
        return self.values

    def get_column_index(self, column_name: str) -> Optional[int]:
        header_row = self.values[0]
        return header_row.index(column_name)

    def _find(self, query_column: str, query_value: str, column: Optional[str] = None) -> Optional[Tuple[int, List[str]]]:
        values = self.update_values()
        query_column_index = self.get_column_index(query_column)
        filtered_rows = [(id + 1,  row) for id, row in enumerate(values[1:]) if row[query_column_index] == query_value]
        if len(filtered_rows) == 0:
            return None

        id, row = filtered_rows.pop()
        if column is None:
            return id, row
        else:
            col_index = self.get_column_index(column)
            return row[col_index]

    def _add_or_update_row(self, query_column: Optional[str], data: Dict[str, str]) -> None:
        values = self.update_values()
        found = self._find(query_column, data[query_column]) if query_column is not None else None
        if query_column is not None and found is None:
            raise ValueError(f"Unable to find `{query_column}`=`{data[query_column]}`")
        row_index = len(values) + 1 if not found else found[0]
        errors = []
        for key, value in data.items():
            try:
                col_index = self.get_column_index(key)
                self.sheet.update_cell(row_index + 1, col_index + 1, value)
            except ValueError:
                errors.append([key, value])
        if len(errors) > 0:
            raise ValueError(f"Undable to update following data due to column not exists: {errors}")

    def find_pagerduty_schedule(self, channel_name: str) -> Optional[str]:
        return self._find("Channel", channel_name, "Pagerduty Schedule")

    def find_oncall_tracking_sheet(self, channel_name: str) -> Optional[str]:
        return self._find("Channel", channel_name, "Tracking Sheet")

    def update_tracking_log(self, query_field: str, query_value: str, request_url: str) -> None:
        self._add_or_update_row(query_field, {query_field: query_value, "request_url": request_url})

    def add_or_update_pagerduty_schedule(self, channel_name: str, pagerduty_schedule: str) -> str:
        try:
            self._add_or_update_row("Channel", {"Channel": channel_name, "Pagerduty Schedule": pagerduty_schedule})
            return "Data updated"
        except ValueError as e:
            return e

    def add_or_update_tracking_sheet(self, channel_name: str, oncall_log_sheet: str) -> str:
        try:
            self._add_or_update_row("Channel", {"Channel": channel_name, "Tracking Sheet": oncall_log_sheet})
            return "Data updated"
        except ValueError as e:
            return e
