from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.airfare_ml.data.schema import enforce_column_order


class BaseSourceAdapter(ABC):
    """
    Base interface for converting source-specific airfare data
    into the canonical airfare observation schema.
    """

    source_name: str

    @abstractmethod
    def parse(self, raw_data) -> pd.DataFrame:
        """
        Convert source-specific raw data into canonical observations.

        Implementations must return a pandas DataFrame containing
        the canonical airfare schema.
        """
        raise NotImplementedError

    def transform(self, raw_data) -> pd.DataFrame:
        """
        Parse and enforce the canonical schema.
        """

        df = self.parse(raw_data)

        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"{self.__class__.__name__}.parse() must return "
                "a pandas DataFrame."
            )

        return enforce_column_order(df)