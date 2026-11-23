from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "1.0.0"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'reap',
     'default_range': 'string',
     'description': 'Machine-readable specification of the pre- and '
                    'post-installation energy evidence submitted with a Rural '
                    'Energy for America Program (REAP) application under 7 CFR '
                    'part 4280 subpart B as amended by 91 FR 62600 (October 1, '
                    '2026). The schema covers the energy quantities, metering '
                    'context and equipment information from which documented '
                    'performance is verified; it does not cover applicant '
                    'financial, ownership or certification documents.',
     'id': 'https://w3id.org/reapschema/reap_evidence',
     'imports': ['linkml:types'],
     'license': 'https://creativecommons.org/licenses/by/4.0/',
     'name': 'reap_evidence',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'reap': {'prefix_prefix': 'reap',
                           'prefix_reference': 'https://w3id.org/reapschema/'},
                  'schema': {'prefix_prefix': 'schema',
                             'prefix_reference': 'http://schema.org/'},
                  'ucum': {'prefix_prefix': 'ucum',
                           'prefix_reference': 'http://unitsofmeasure.org/'}},
     'source_file': '/Users/avingupta/Documents/research/reap-reporting-design/src/reapschema/schema/reap_evidence.yaml',
     'title': 'REAP performance-evidence schema'} )

class ApplicantType(str, Enum):
    """
    Entity type under which the applicant applies (section 4280.131(a)(8)).
    """
    agricultural_producer = "agricultural_producer"
    rural_small_business = "rural_small_business"


class ProjectCategory(str, Enum):
    """
    Project type declared under section 4280.131(b)(2).
    """
    RES = "RES"
    """
    Renewable energy system.
    """
    EEI = "EEI"
    """
    Energy efficiency improvement.
    """


class ResSubcategory(str, Enum):
    """
    Subcategory of a renewable energy system (definition in section 4280.104).
    """
    energy_replacement = "energy_replacement"
    """
    Replaces 120 percent or less of annual energy use in the 12 months before installation.
    """
    energy_generation = "energy_generation"
    """
    Produces more than 120 percent of annual energy use in the 12 months before installation.
    """
    retrofit = "retrofit"
    distribution_or_ancillary = "distribution_or_ancillary"


class TechnologyClass(str, Enum):
    """
    Controlled vocabulary of technologies. RES values follow section 4280.122(a)(8)(i)(B) and the definitions of section 4280.104; EEI values are measure classes commonly funded and are not enumerated in the rule.
    """
    solar_electric = "solar_electric"
    solar_thermal = "solar_thermal"
    wind = "wind"
    biomass = "biomass"
    bioenergy = "bioenergy"
    anaerobic_digester = "anaerobic_digester"
    geothermal_direct_generation = "geothermal_direct_generation"
    geothermal_electric_generation = "geothermal_electric_generation"
    hydrogen = "hydrogen"
    hydroelectric = "hydroelectric"
    ocean_energy = "ocean_energy"
    hybrid = "hybrid"
    eei_lighting = "eei_lighting"
    eei_hvac = "eei_hvac"
    eei_refrigeration = "eei_refrigeration"
    eei_building_envelope = "eei_building_envelope"
    eei_motors_pumps = "eei_motors_pumps"
    eei_grain_drying = "eei_grain_drying"
    eei_irrigation = "eei_irrigation"
    eei_other = "eei_other"


class MeterType(str, Enum):
    utility_revenue_meter = "utility_revenue_meter"
    """
    Utility billing meter at the service point.
    """
    inverter = "inverter"
    """
    Production measured at the point of electrical coupling of the RES.
    """
    sub_meter = "sub_meter"
    """
    Customer-owned meter on a circuit or piece of equipment.
    """


class NettingArrangement(str, Enum):
    """
    Metering agreement type (section 4280.122(a)(8)(i)(F)(3)).
    """
    none = "none"
    """
    No export crediting; the meter registers delivered energy only.
    """
    conventional_net_metering = "conventional_net_metering"
    """
    Exports offset imports within the billing period; the bill may show a single net quantity.
    """
    net_billing = "net_billing"
    """
    Imports and exports are metered and valued separately.
    """
    aggregate_net_metering = "aggregate_net_metering"
    """
    Exports are credited across several meters of the same customer.
    """
    virtual_net_metering = "virtual_net_metering"
    """
    Credits from an off-site or shared system are allocated to the account.
    """
    off_grid = "off_grid"
    """
    No utility interconnection.
    """


class BilledQuantityBasis(str, Enum):
    """
    Whether billed energy on a utility record is net of exports.
    """
    delivered_only = "delivered_only"
    """
    Energy delivered by the utility (imports); exports reported separately or absent.
    """
    net_of_exports = "net_of_exports"
    """
    Imports minus exports within the billing period.
    """


class ReadType(str, Enum):
    actual = "actual"
    estimated = "estimated"


class EnergyUnit(str, Enum):
    """
    Energy units as UCUM codes.
    """
    kWFULL_STOPh = "kW.h"
    """
    Kilowatt-hour.
    """
    MWFULL_STOPh = "MW.h"
    """
    Megawatt-hour.
    """
    LEFT_SQUARE_BRACKETBtu_ITRIGHT_SQUARE_BRACKET = "[Btu_IT]"
    """
    British thermal unit (International Table).
    """
    kLEFT_SQUARE_BRACKETBtu_ITRIGHT_SQUARE_BRACKET = "k[Btu_IT]"
    """
    Thousand Btu.
    """
    MLEFT_SQUARE_BRACKETBtu_ITRIGHT_SQUARE_BRACKET = "M[Btu_IT]"
    """
    Million Btu.
    """
    LEFT_SQUARE_BRACKETtherm_usRIGHT_SQUARE_BRACKET = "[therm_us]"
    """
    U.S. therm (100,000 Btu).
    """


class PowerUnit(str, Enum):
    kW = "kW"
    """
    Kilowatt.
    """
    MW = "MW"
    """
    Megawatt.
    """


class ClaimQuantity(str, Enum):
    annual_energy_production = "annual_energy_production"
    """
    Annual energy production of an RES as defined in section 4280.104.
    """
    annual_energy_savings = "annual_energy_savings"
    """
    Annual energy saved by an EEI (pre-installation minus post-installation use).
    """


class ClaimMethod(str, Enum):
    """
    How the claimed quantity was obtained.
    """
    metered_production = "metered_production"
    """
    Sum of production-meter (inverter) readings over the post-installation period.
    """
    billing_difference = "billing_difference"
    """
    Pre-installation minus post-installation billed energy.
    """
    regression_normalized = "regression_normalized"
    """
    Degree-day or other regression baseline adjusted to post-period or normal-year conditions.
    """
    engineering_estimate = "engineering_estimate"
    """
    Calculated from rated capacity or equipment specifications rather than measured data.
    """


class NormalizationBasis(str, Enum):
    none = "none"
    post_period_weather = "post_period_weather"
    """
    Baseline adjusted to post-installation weather (avoided energy use).
    """
    normal_year_weather = "normal_year_weather"
    """
    Both periods adjusted to long-term normal weather.
    """


class CollectionMode(str, Enum):
    """
    How the energy records were captured for submission.
    """
    manual_transcription = "manual_transcription"
    utility_file_upload = "utility_file_upload"
    green_button_download = "green_button_download"
    """
    Customer download in the NAESB REQ.21 ESPI ("Green Button") format.
    """
    automated_utility_access = "automated_utility_access"
    """
    Records retrieved from the utility under customer authorization.
    """



class Applicant(ConfiguredBaseModel):
    """
    Legal entity submitting the application.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant', 'Facility', 'Project', 'Meter', 'EvidencePackage']} })
    legal_name: str = Field(default=..., description="""Legal name of the applicant (section 4280.131(a)(1)).""", json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant']} })
    applicant_type: ApplicantType = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant']} })
    unique_entity_identifier: Optional[str] = Field(default=None, description="""Unique Entity Identifier from SAM.gov (section 4280.131(a)(3)).""", json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant']} })

    @field_validator('unique_entity_identifier')
    def pattern_unique_entity_identifier(cls, v):
        pattern=re.compile(r"^[A-Z0-9]{12}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid unique_entity_identifier format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid unique_entity_identifier format: {v}"
            raise ValueError(err_msg)
        return v


class Facility(ConfiguredBaseModel):
    """
    Site at which the project is installed.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant', 'Facility', 'Project', 'Meter', 'EvidencePackage']} })
    address: str = Field(default=..., description="""Street address of the project location (section 4280.131(b)(11)).""", json_schema_extra = { "linkml_meta": {'domain_of': ['Facility']} })
    state: str = Field(default=..., description="""Two-letter State or territory code.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Facility']} })
    latitude: Optional[float] = Field(default=None, ge=-90, le=90, json_schema_extra = { "linkml_meta": {'domain_of': ['Facility'], 'unit': {'ucum_code': 'deg'}} })
    longitude: Optional[float] = Field(default=None, ge=-180, le=180, json_schema_extra = { "linkml_meta": {'domain_of': ['Facility'], 'unit': {'ucum_code': 'deg'}} })
    climate_zone: Optional[int] = Field(default=None, description="""IECC/ASHRAE 169 thermal climate zone number.""", ge=1, le=8, json_schema_extra = { "linkml_meta": {'domain_of': ['Facility']} })
    weather_station_id: Optional[str] = Field(default=None, description="""Identifier (USAF-WBAN) of the nearest weather station used for degree days.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Facility']} })

    @field_validator('state')
    def pattern_state(cls, v):
        pattern=re.compile(r"^[A-Z]{2}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid state format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid state format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('weather_station_id')
    def pattern_weather_station_id(cls, v):
        pattern=re.compile(r"^[0-9A-Z]{6}-[0-9]{5}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid weather_station_id format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid weather_station_id format: {v}"
            raise ValueError(err_msg)
        return v


class Project(ConfiguredBaseModel):
    """
    Completed RES or EEI for which the award is requested.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence',
         'rules': [{'description': 'An RES declares its rated system size with a unit.',
                    'postconditions': {'slot_conditions': {'rated_capacity': {'name': 'rated_capacity',
                                                                              'required': True},
                                                           'rated_capacity_unit': {'name': 'rated_capacity_unit',
                                                                                   'required': True}}},
                    'preconditions': {'slot_conditions': {'category': {'equals_string': 'RES',
                                                                       'name': 'category'}}}}]})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant', 'Facility', 'Project', 'Meter', 'EvidencePackage']} })
    category: ProjectCategory = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    res_subcategory: Optional[ResSubcategory] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    technology: TechnologyClass = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    rated_capacity: Optional[float] = Field(default=None, description="""Rated system size (section 4280.131(b)(13)).""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    rated_capacity_unit: Optional[PowerUnit] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    in_service_date: date = Field(default=..., description="""Date the RES or EEI was installed and operational.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    project_period_start: Optional[date] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    project_period_end: Optional[date] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    project_cost: Optional[float] = Field(default=None, description="""Total project cost in U.S. dollars.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Project'], 'unit': {'ucum_code': '[USD]'}} })
    amount_requested: Optional[float] = Field(default=None, description="""Federal award requested in U.S. dollars (section 4280.122(a)(2)).""", ge=1500, le=500000, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    useful_life_years: Optional[float] = Field(default=None, ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Project'], 'unit': {'ucum_code': 'a'}} })
    array_tilt: Optional[float] = Field(default=None, description="""Tilt of a fixed photovoltaic array from horizontal.""", ge=0, le=90, json_schema_extra = { "linkml_meta": {'domain_of': ['Project'], 'unit': {'ucum_code': 'deg'}} })
    array_azimuth: Optional[float] = Field(default=None, description="""Azimuth of a fixed photovoltaic array, degrees clockwise from north.""", ge=0, le=360, json_schema_extra = { "linkml_meta": {'domain_of': ['Project'], 'unit': {'ucum_code': 'deg'}} })
    storage_capacity: Optional[float] = Field(default=None, description="""Rated power of a paired energy storage system.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })
    affected_end_use_share: Optional[float] = Field(default=None, description="""Share of pre-installation annual energy use attributable to the end uses the EEI modifies, from the Energy Assessment or Energy Audit.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['Project']} })


class Meter(ConfiguredBaseModel):
    """
    Device whose readings document energy use or production.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant', 'Facility', 'Project', 'Meter', 'EvidencePackage']} })
    meter_type: MeterType = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Meter']} })
    netting_arrangement: Optional[NettingArrangement] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Meter']} })
    billed_quantity_basis: Optional[BilledQuantityBasis] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Meter']} })
    dedicated: Optional[bool] = Field(default=None, description="""Whether the meter serves only the project facility (section 4280.122(a)(16)).""", json_schema_extra = { "linkml_meta": {'domain_of': ['Meter']} })
    utility_account: Optional[str] = Field(default=None, description="""Utility account or meter number as printed on the bill.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Meter']} })
    interval_minutes: Optional[int] = Field(default=None, description="""Length of the recording interval for interval data.""", ge=1, le=1440, json_schema_extra = { "linkml_meta": {'domain_of': ['Meter', 'IntervalSeries']} })


class BillingRecord(ConfiguredBaseModel):
    """
    One billing-period record of a utility revenue meter, or one period reading of a production meter.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence',
         'slot_usage': {'meter': {'inlined': False, 'name': 'meter'}}})

    meter: str = Field(default=..., description="""Meter to which a record belongs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord', 'IntervalSeries']} })
    is_pre_installation: bool = Field(default=..., description="""True for records in the 12 months before installation.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord', 'IntervalSeries']} })
    period_start: Optional[date] = Field(default=None, description="""First day of the billing period (inclusive).""", json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord']} })
    period_end: Optional[date] = Field(default=None, description="""Last day of the billing period (inclusive).""", json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord']} })
    read_type: Optional[ReadType] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord']} })
    energy_imported: float = Field(default=..., description="""Energy delivered by the utility in the period (or net energy when the basis is net_of_exports).""", json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord']} })
    energy_exported: Optional[float] = Field(default=None, description="""Energy exported to the utility in the period.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord']} })
    energy_unit: EnergyUnit = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord', 'IntervalSeries', 'PerformanceClaim']} })
    peak_demand: Optional[float] = Field(default=None, description="""Billed peak demand in the period.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord'], 'unit': {'ucum_code': 'kW'}} })
    energy_charge: Optional[float] = Field(default=None, description="""Energy charges in U.S. dollars, excluding fixed meter charges, demand charges, subsidy charges and sales tax (definition of Simple Payback, section 4280.104).""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord'], 'unit': {'ucum_code': '[USD]'}} })


class IntervalSeries(ConfiguredBaseModel):
    """
    Regular time series of interval energy from one meter.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence',
         'slot_usage': {'interval_minutes': {'name': 'interval_minutes',
                                             'required': True},
                        'meter': {'inlined': False, 'name': 'meter'}}})

    meter: str = Field(default=..., description="""Meter to which a record belongs.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord', 'IntervalSeries']} })
    is_pre_installation: bool = Field(default=..., description="""True for records in the 12 months before installation.""", json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord', 'IntervalSeries']} })
    start_time: datetime  = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['IntervalSeries']} })
    time_zone: str = Field(default=..., description="""IANA time zone or fixed UTC offset of the timestamps.""", json_schema_extra = { "linkml_meta": {'domain_of': ['IntervalSeries']} })
    interval_minutes: int = Field(default=..., description="""Length of the recording interval for interval data.""", ge=1, le=1440, json_schema_extra = { "linkml_meta": {'domain_of': ['Meter', 'IntervalSeries']} })
    energy_unit: EnergyUnit = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord', 'IntervalSeries', 'PerformanceClaim']} })
    values: list[float] = Field(default=..., description="""Energy per interval in chronological order.""", json_schema_extra = { "linkml_meta": {'domain_of': ['IntervalSeries']} })


class PerformanceClaim(ConfiguredBaseModel):
    """
    The applicant's stated annual production or savings and its basis.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence'})

    quantity: ClaimQuantity = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })
    claimed_value: float = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })
    energy_unit: EnergyUnit = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['BillingRecord', 'IntervalSeries', 'PerformanceClaim']} })
    method: Optional[ClaimMethod] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })
    normalization_basis: Optional[NormalizationBasis] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })
    relative_uncertainty: Optional[float] = Field(default=None, description="""Relative standard uncertainty of the claimed value.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })
    pre_period_energy: Optional[float] = Field(default=None, description="""Energy used in the 12 consecutive months before installation (section 4280.131(b)(17)(i)).""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })
    post_period_energy: Optional[float] = Field(default=None, description="""Energy used (EEI) or produced (RES) in the 12 months after installation.""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })
    energy_price: Optional[float] = Field(default=None, description="""Average price of energy in U.S. dollars per unit (section 4280.131(b)(17)(ii)).""", ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['PerformanceClaim']} })


class EquipmentItem(ConfiguredBaseModel):
    """
    Equipment acquired for the project (Equipment report, section 4280.160(c); country of origin, section 4280.131(b)(5)).
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence'})

    make: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentItem']} })
    model: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentItem']} })
    item_quantity: int = Field(default=..., ge=1, json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentItem']} })
    component_role: Optional[str] = Field(default=None, description="""Function of the item in the system (module, inverter, turbine, luminaire, ...).""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentItem']} })
    country_of_origin: Optional[str] = Field(default=None, description="""ISO 3166-1 alpha-2 country code of manufacture (section 4280.131(b)(5)).""", json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentItem']} })
    acquisition_cost: Optional[float] = Field(default=None, ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentItem']} })
    acquisition_date: Optional[date] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['EquipmentItem']} })

    @field_validator('country_of_origin')
    def pattern_country_of_origin(cls, v):
        pattern=re.compile(r"^[A-Z]{2}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid country_of_origin format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid country_of_origin format: {v}"
            raise ValueError(err_msg)
        return v


class EvidencePackage(ConfiguredBaseModel):
    """
    Complete performance evidence for one application.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/reapschema/reap_evidence', 'tree_root': True})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Applicant', 'Facility', 'Project', 'Meter', 'EvidencePackage']} })
    collection_mode: Optional[CollectionMode] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    applicant: Applicant = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    facility: Facility = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    project: Project = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    meters: list[Meter] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    billing_records: Optional[list[BillingRecord]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    interval_series: Optional[list[IntervalSeries]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    performance_claim: PerformanceClaim = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })
    equipment: Optional[list[EquipmentItem]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['EvidencePackage']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Applicant.model_rebuild()
Facility.model_rebuild()
Project.model_rebuild()
Meter.model_rebuild()
BillingRecord.model_rebuild()
IntervalSeries.model_rebuild()
PerformanceClaim.model_rebuild()
EquipmentItem.model_rebuild()
EvidencePackage.model_rebuild()
