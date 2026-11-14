"""Load byte-preserved v6 offline modules; no generation runner is included."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
BASE=ROOT/'frozen_v6'
sys.path.insert(0,str(BASE))
import table_binding as binding_v2
import pipeline_v5 as pipeline_v6
from pilot_calculator import calculate_v4
from calculator_v2 import normalize_year
