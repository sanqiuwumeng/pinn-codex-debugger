## ADDED Requirements

### Requirement: Every physical parameter preserves raw and canonical forms
The system SHALL record each physical parameter's meaning, quantity kind, raw value, raw unit, model-canonical value, model-canonical unit, declared unit-system identity, dimensional signature, conversion factor, source and confirmation status.

#### Scenario: Density differs from the model's declared internal unit
- **WHEN** a source provides density as `4430 kg/m^3` and the model declares `g/cm^3` for density
- **THEN** the audit records both representations and the explicit conversion factor without treating the non-SI model unit as an error

### Requirement: The user model declares its internal unit system
The system SHALL resolve canonical units from an explicit model-scoped unit-system contract rather than from global SI defaults or a domain-specific guess.

#### Scenario: A model consistently uses millimetres
- **WHEN** geometry, coordinates, source locations and derivative scales declare `mm` as the model length unit
- **THEN** the audit accepts `mm` as canonical for that model and does not require conversion to metres

#### Scenario: Metres and millimetres are mixed with a complete conversion
- **WHEN** one source provides a length in metres, the model uses millimetres internally and the load path applies the correct factor of `1000`
- **THEN** the audit passes the conversion chain and preserves both units

#### Scenario: Metres and millimetres are mixed without conversion
- **WHEN** a metre-valued geometry parameter reaches a millimetre-based PDE or sampling path without a declared conversion
- **THEN** the audit returns `REJECT` with the source, load site, use site and missing factor

### Requirement: Unit conversion does not overwrite user configuration
The system SHALL write a derived, traceable parameter manifest and MUST NOT silently replace values or units in the user's original files.

#### Scenario: A parameter requires conversion
- **WHEN** the audit can convert a confirmed raw unit to the internal unit system
- **THEN** it writes the converted value to a new manifest while leaving the source file byte-identical

### Requirement: Parameter use is traced from source to governing equation
The physical audit SHALL record configuration source, load site, existing conversion operations and final PDE/BC/IC use sites before judging consistency.

#### Scenario: Code already converts a heat-transfer coefficient
- **WHEN** the configuration stores `h` in `W/(mm^2 K)` and the load path already multiplies by `10^6`
- **THEN** the auditor reports the existing conversion and prevents a second automatic conversion

#### Scenario: A non-thermal coefficient already has a conversion
- **WHEN** an elasticity or fluid model converts a coefficient into its declared model unit before PDE use
- **THEN** the same conversion-chain rule applies without requiring a heat-transfer-specific audit path

### Requirement: Governing equations are dimensionally consistent
The system SHALL verify that all additive terms in each PDE, boundary condition, initial condition, source expression and derived constitutive equation share compatible dimensions.

#### Scenario: Volumetric heat source is supplied as surface heat flux
- **WHEN** a term with dimension `W/m^2` is inserted where the equation requires `W/m^3`
- **THEN** the audit returns `REJECT` with the equation term and source location

### Requirement: Semantic unit distinctions are validated
The system SHALL distinguish dimensionally related but semantically non-interchangeable quantities including absolute versus differential temperature, frequency versus angular frequency and surface versus volumetric sources.

#### Scenario: Celsius is used in a radiation term
- **WHEN** a temperature expressed in degrees Celsius is used directly in a `T^4` radiation expression
- **THEN** the audit rejects the expression until an absolute-temperature conversion is confirmed

### Requirement: Nondimensional derivative scaling is audited
For normalized PINN coordinates, the system SHALL verify chain-rule factors for temporal and spatial derivatives, boundary normals, source geometry and output scaling.

#### Scenario: A second spatial derivative uses normalized coordinates
- **WHEN** `x_hat=(x-x0)/L` is differentiated twice in the PDE residual
- **THEN** the audit verifies the physical residual includes the required `1/L^2` scaling

### Requirement: Magnitude checks provide evidence without fabricating values
The system SHALL compare canonical parameters against configured or domain-approved plausible ranges but MUST NOT replace an outlier with a guessed value.

#### Scenario: Specific heat is three orders of magnitude below the expected scale
- **WHEN** the numeric value suggests `J/(g K)` was interpreted as `J/(kg K)`
- **THEN** the audit reports the suspected unit conflict and requests confirmation instead of correcting it silently

### Requirement: Ambiguous or missing units block experimentation
The audit SHALL return one of `PASS`, `WARN`, `REJECT` or `NEEDS_UNIT_CONFIRMATION`, and only `PASS` SHALL automatically permit the next preflight stage.

#### Scenario: A user provides a conductivity value without a unit
- **WHEN** code and documentation do not establish a unique unit
- **THEN** the workflow enters `NEEDS_UNIT_CONFIRMATION` and does not start baseline or training work

#### Scenario: The audit returns a warning
- **WHEN** all dimensions are consistent but a magnitude or semantic risk remains
- **THEN** continuation requires an explicit user approval record
