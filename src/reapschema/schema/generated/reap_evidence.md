# REAP performance-evidence schema

Machine-readable specification of the pre- and post-installation energy evidence submitted with a Rural Energy for America Program (REAP) application under 7 CFR part 4280 subpart B as amended by 91 FR 62600 (October 1, 2026). The schema covers the energy quantities, metering context and equipment information from which documented performance is verified; it does not cover applicant financial, ownership or certification documents.

Schema version 1.0.0.

## Applicant

Legal entity submitting the application.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `id` | string | yes | no |  |  |
| `legal_name` | string | yes | no |  | Legal name of the applicant (section 4280.131(a)(1)). |
| `applicant_type` | ApplicantType | yes | no |  |  |
| `unique_entity_identifier` | string | no | no |  | Unique Entity Identifier from SAM.gov (section 4280.131(a)(3)). |

## Facility

Site at which the project is installed.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `id` | string | yes | no |  |  |
| `address` | string | yes | no |  | Street address of the project location (section 4280.131(b)(11)). |
| `state` | string | yes | no |  | Two-letter State or territory code. |
| `latitude` | float | no | no | deg |  |
| `longitude` | float | no | no | deg |  |
| `climate_zone` | integer | no | no |  | IECC/ASHRAE 169 thermal climate zone number. |
| `weather_station_id` | string | no | no |  | Identifier (USAF-WBAN) of the nearest weather station used for degree days. |

## Project

Completed RES or EEI for which the award is requested.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `id` | string | yes | no |  |  |
| `category` | ProjectCategory | yes | no |  |  |
| `res_subcategory` | ResSubcategory | no | no |  |  |
| `technology` | TechnologyClass | yes | no |  |  |
| `rated_capacity` | float | no | no |  | Rated system size (section 4280.131(b)(13)). |
| `rated_capacity_unit` | PowerUnit | no | no |  |  |
| `in_service_date` | date | yes | no |  | Date the RES or EEI was installed and operational. |
| `project_period_start` | date | no | no |  |  |
| `project_period_end` | date | no | no |  |  |
| `project_cost` | float | no | no | [USD] | Total project cost in U.S. dollars. |
| `amount_requested` | float | no | no |  | Federal award requested in U.S. dollars (section 4280.122(a)(2)). |
| `useful_life_years` | float | no | no | a |  |
| `array_tilt` | float | no | no | deg | Tilt of a fixed photovoltaic array from horizontal. |
| `array_azimuth` | float | no | no | deg | Azimuth of a fixed photovoltaic array, degrees clockwise from north. |
| `storage_capacity` | float | no | no |  | Rated power of a paired energy storage system. |
| `affected_end_use_share` | float | no | no |  | Share of pre-installation annual energy use attributable to the end uses the EEI modifies, from the Energy Assessment or Energy Audit. |

## Meter

Device whose readings document energy use or production.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `id` | string | yes | no |  |  |
| `meter_type` | MeterType | yes | no |  |  |
| `netting_arrangement` | NettingArrangement | no | no |  |  |
| `billed_quantity_basis` | BilledQuantityBasis | no | no |  |  |
| `dedicated` | boolean | no | no |  | Whether the meter serves only the project facility (section 4280.122(a)(16)). |
| `utility_account` | string | no | no |  | Utility account or meter number as printed on the bill. |
| `interval_minutes` | integer | no | no |  | Length of the recording interval for interval data. |

## BillingRecord

One billing-period record of a utility revenue meter, or one period reading of a production meter.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `meter` | Meter | yes | no |  | Meter to which a record belongs. |
| `is_pre_installation` | boolean | yes | no |  | True for records in the 12 months before installation. |
| `period_start` | date | no | no |  | First day of the billing period (inclusive). |
| `period_end` | date | no | no |  | Last day of the billing period (inclusive). |
| `read_type` | ReadType | no | no |  |  |
| `energy_imported` | float | yes | no |  | Energy delivered by the utility in the period (or net energy when the basis is net_of_exports). |
| `energy_exported` | float | no | no |  | Energy exported to the utility in the period. |
| `energy_unit` | EnergyUnit | yes | no |  |  |
| `peak_demand` | float | no | no | kW | Billed peak demand in the period. |
| `energy_charge` | float | no | no | [USD] | Energy charges in U.S. dollars, excluding fixed meter charges, demand charges, subsidy charges and sales tax (definition of Simple Payback, section 4280.104). |

## IntervalSeries

Regular time series of interval energy from one meter.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `meter` | Meter | yes | no |  | Meter to which a record belongs. |
| `is_pre_installation` | boolean | yes | no |  | True for records in the 12 months before installation. |
| `start_time` | datetime | yes | no |  |  |
| `time_zone` | string | yes | no |  | IANA time zone or fixed UTC offset of the timestamps. |
| `interval_minutes` | integer | yes | no |  | Length of the recording interval for interval data. |
| `energy_unit` | EnergyUnit | yes | no |  |  |
| `values` | float | yes | yes |  | Energy per interval in chronological order. |

## PerformanceClaim

The applicant's stated annual production or savings and its basis.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `quantity` | ClaimQuantity | yes | no |  |  |
| `claimed_value` | float | yes | no |  |  |
| `energy_unit` | EnergyUnit | yes | no |  |  |
| `method` | ClaimMethod | no | no |  |  |
| `normalization_basis` | NormalizationBasis | no | no |  |  |
| `relative_uncertainty` | float | no | no |  | Relative standard uncertainty of the claimed value. |
| `pre_period_energy` | float | no | no |  | Energy used in the 12 consecutive months before installation (section 4280.131(b)(17)(i)). |
| `post_period_energy` | float | no | no |  | Energy used (EEI) or produced (RES) in the 12 months after installation. |
| `energy_price` | float | no | no |  | Average price of energy in U.S. dollars per unit (section 4280.131(b)(17)(ii)). |

## EquipmentItem

Equipment acquired for the project (Equipment report, section 4280.160(c); country of origin, section 4280.131(b)(5)).

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `make` | string | yes | no |  |  |
| `model` | string | yes | no |  |  |
| `item_quantity` | integer | yes | no |  |  |
| `component_role` | string | no | no |  | Function of the item in the system (module, inverter, turbine, luminaire, ...). |
| `country_of_origin` | string | no | no |  | ISO 3166-1 alpha-2 country code of manufacture (section 4280.131(b)(5)). |
| `acquisition_cost` | float | no | no |  |  |
| `acquisition_date` | date | no | no |  |  |

## EvidencePackage

Complete performance evidence for one application.

| Element | Range | Required | Multivalued | Unit | Description |
|---|---|---|---|---|---|
| `id` | string | yes | no |  |  |
| `collection_mode` | CollectionMode | no | no |  |  |
| `applicant` | Applicant | yes | no |  |  |
| `facility` | Facility | yes | no |  |  |
| `project` | Project | yes | no |  |  |
| `meters` | Meter | yes | yes |  |  |
| `billing_records` | BillingRecord | no | yes |  |  |
| `interval_series` | IntervalSeries | no | yes |  |  |
| `performance_claim` | PerformanceClaim | yes | no |  |  |
| `equipment` | EquipmentItem | no | yes |  |  |

## Enumerations

### ApplicantType

Entity type under which the applicant applies (section 4280.131(a)(8)).

- `agricultural_producer`
- `rural_small_business`

### ProjectCategory

Project type declared under section 4280.131(b)(2).

- `RES`: Renewable energy system.
- `EEI`: Energy efficiency improvement.

### ResSubcategory

Subcategory of a renewable energy system (definition in section 4280.104).

- `energy_replacement`: Replaces 120 percent or less of annual energy use in the 12 months before installation.
- `energy_generation`: Produces more than 120 percent of annual energy use in the 12 months before installation.
- `retrofit`
- `distribution_or_ancillary`

### TechnologyClass

Controlled vocabulary of technologies. RES values follow section 4280.122(a)(8)(i)(B) and the definitions of section 4280.104; EEI values are measure classes commonly funded and are not enumerated in the rule.

- `solar_electric`
- `solar_thermal`
- `wind`
- `biomass`
- `bioenergy`
- `anaerobic_digester`
- `geothermal_direct_generation`
- `geothermal_electric_generation`
- `hydrogen`
- `hydroelectric`
- `ocean_energy`
- `hybrid`
- `eei_lighting`
- `eei_hvac`
- `eei_refrigeration`
- `eei_building_envelope`
- `eei_motors_pumps`
- `eei_grain_drying`
- `eei_irrigation`
- `eei_other`

### MeterType



- `utility_revenue_meter`: Utility billing meter at the service point.
- `inverter`: Production measured at the point of electrical coupling of the RES.
- `sub_meter`: Customer-owned meter on a circuit or piece of equipment.

### NettingArrangement

Metering agreement type (section 4280.122(a)(8)(i)(F)(3)).

- `none`: No export crediting; the meter registers delivered energy only.
- `conventional_net_metering`: Exports offset imports within the billing period; the bill may show a single net quantity.
- `net_billing`: Imports and exports are metered and valued separately.
- `aggregate_net_metering`: Exports are credited across several meters of the same customer.
- `virtual_net_metering`: Credits from an off-site or shared system are allocated to the account.
- `off_grid`: No utility interconnection.

### BilledQuantityBasis

Whether billed energy on a utility record is net of exports.

- `delivered_only`: Energy delivered by the utility (imports); exports reported separately or absent.
- `net_of_exports`: Imports minus exports within the billing period.

### ReadType



- `actual`
- `estimated`

### EnergyUnit

Energy units as UCUM codes.

- `kW.h`: Kilowatt-hour.
- `MW.h`: Megawatt-hour.
- `[Btu_IT]`: British thermal unit (International Table).
- `k[Btu_IT]`: Thousand Btu.
- `M[Btu_IT]`: Million Btu.
- `[therm_us]`: U.S. therm (100,000 Btu).

### PowerUnit



- `kW`: Kilowatt.
- `MW`: Megawatt.

### ClaimQuantity



- `annual_energy_production`: Annual energy production of an RES as defined in section 4280.104.
- `annual_energy_savings`: Annual energy saved by an EEI (pre-installation minus post-installation use).

### ClaimMethod

How the claimed quantity was obtained.

- `metered_production`: Sum of production-meter (inverter) readings over the post-installation period.
- `billing_difference`: Pre-installation minus post-installation billed energy.
- `regression_normalized`: Degree-day or other regression baseline adjusted to post-period or normal-year conditions.
- `engineering_estimate`: Calculated from rated capacity or equipment specifications rather than measured data.

### NormalizationBasis



- `none`
- `post_period_weather`: Baseline adjusted to post-installation weather (avoided energy use).
- `normal_year_weather`: Both periods adjusted to long-term normal weather.

### CollectionMode

How the energy records were captured for submission.

- `manual_transcription`
- `utility_file_upload`
- `green_button_download`: Customer download in the NAESB REQ.21 ESPI ("Green Button") format.
- `automated_utility_access`: Records retrieved from the utility under customer authorization.
