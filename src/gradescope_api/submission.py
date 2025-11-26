from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

import pytz
from bs4 import BeautifulSoup
from dateutil.parser import parse

if TYPE_CHECKING:
    from gradescope_api.client import GradescopeClient
    from gradescope_api.assignment import GradescopeAssignment
    from gradescope_api.student import GradescopeStudent

class GradescopeSubmission:
    def __init__(
        self,
        _client: GradescopeClient,
        _course_id: str,
        _assignment: GradescopeAssignment,
        _student: GradescopeStudent,
        submission_id: str,
    ) -> None:
        self._client = _client
        self._course_id = _course_id
        self._assignment = _assignment
        self._student = _student
        self.submission_id = submission_id

    def get_url(self) -> str:
        return self._assignment.get_url() + f"/submissions/{self.submission_id}"
