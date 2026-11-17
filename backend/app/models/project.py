"""Pydantic v2 schemas for the project JSON (prompt section 3). Internal units: mg/L, C, m3/h, bar."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ION_KEYS = ["Na", "Ca", "Mg", "K", "Ba", "Sr", "NH4", "B", "Cl", "CO3", "HCO3", "F", "NO3", "SO4", "SiO2"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ProjectInfo(_Base):
    name: str = ""
    date: str = ""
    designedBy: str = "Untitled"
    company: str = "Untitled"


class Water(_Base):
    inputUnit: Literal["mg/L", "ppmCaCO3", "meq/L"] = "mg/L"
    specifyIndividualSolutes: bool = True
    tdsInput: Optional[float] = None
    temperatureC: float = 25
    pH: float = 7.5
    waterType: str = "RO Permeate SDI < 1"
    ions: dict[str, float] = Field(default_factory=lambda: {k: 0.0 for k in ION_KEYS})


class PhAdjust(_Base):
    chemical: Literal["H2SO4", "HCl"] = "H2SO4"
    targetPH: float = 7.5


class Softening(_Base):
    caLeakage: float = 0.1
    mgLeakage: float = 0.1


class Scaling(_Base):
    recoveryPct: float = 15
    temperatureC: float = 25
    option: Literal["none", "ph_adjust", "softening", "antiscalant"] = "none"
    phAdjust: PhAdjust = Field(default_factory=PhAdjust)
    softening: Softening = Field(default_factory=Softening)


class Stage(_Base):
    vessels: int = 1
    elementsPerVessel: int = 1
    elementModel: str = "LP22-8040"
    backPressure: float = 0  # bar


class Pass(_Base):
    stages: list[Stage] = Field(default_factory=lambda: [Stage()])
    sameElementInPass: bool = True
    sameBackPressure: bool = True


class Recycle(_Base):
    enabled: bool = False
    flow: float = 0  # m3/h


class Design(_Base):
    unitSet: Literal["gpd_psi", "gpm_psi", "m3h_bar", "m3d_bar"] = "gpm_psi"
    recoveryPct: float = 15
    permeateFlow: float = 1.1355  # m3/h (= 5 gpm)
    feedTempC: float = 25
    foulingFactor: float = 0.85
    passes: list[Pass] = Field(default_factory=lambda: [Pass()])
    pumpEfficiencyEnabled: bool = False
    pumpEfficiencyPct: float = 80
    intakeBothEnds: bool = False
    frontEndPct: float = 50
    recycle: Recycle = Field(default_factory=Recycle)


class Project(_Base):
    version: str = "1.0"
    project: ProjectInfo = Field(default_factory=ProjectInfo)
    water: Water = Field(default_factory=Water)
    scaling: Scaling = Field(default_factory=Scaling)
    design: Design = Field(default_factory=Design)
    results: dict = Field(default_factory=dict)


class WaterScalingRequest(_Base):
    water: Water
    scaling: Scaling
