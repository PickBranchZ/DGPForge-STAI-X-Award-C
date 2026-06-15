"""Pydantic schema for DGPForge contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1.0"
CROSS_SECTIONAL_ATE_TEMPLATE = "cross_sectional_binary_treatment_continuous_outcome"
CROSS_SECTIONAL_BINARY_OUTCOME_TEMPLATE = "cross_sectional_binary_treatment_binary_outcome"
CROSS_SECTIONAL_COUNT_OUTCOME_TEMPLATE = "cross_sectional_binary_treatment_count_outcome"
TEMPLATE_REGISTRY = {
    CROSS_SECTIONAL_ATE_TEMPLATE: "Cross-sectional binary-treatment continuous-outcome marginal ATE",
    CROSS_SECTIONAL_BINARY_OUTCOME_TEMPLATE: "Cross-sectional binary-treatment binary-outcome marginal estimands",
    CROSS_SECTIONAL_COUNT_OUTCOME_TEMPLATE: "Cross-sectional binary-treatment count/rate outcome marginal estimands",
}

TemplateName = Literal[
    "cross_sectional_binary_treatment_continuous_outcome",
    "cross_sectional_binary_treatment_binary_outcome",
    "cross_sectional_binary_treatment_count_outcome",
]
EstimatorName = Literal[
    "naive_difference",
    "adjusted_ols",
    "adjusted_ols_omit_confounder",
    "ipw",
    "ipw_omit_confounder",
    "aipw",
    "aipw_ps_misspecified",
    "aipw_outcome_misspecified",
    "aipw_double_misspecified",
    "naive_risk_difference",
    "logistic_gcomp_risk_difference",
    "ipw_risk_difference",
    "aipw_risk_difference",
    "adjusted_oracle_includes_U",
    "naive_rate_difference",
    "poisson_offset_gcomp_rate_difference",
    "ipw_rate_difference",
    "naive_difference_complete_case",
    "adjusted_ols_complete_case",
    "aipw_complete_case",
    "adjusted_ols_missingness_ipw",
    "logistic_gcomp_complete_case",
    "rate_gcomp_complete_case",
    "adjusted_ols_naive_se",
    "adjusted_ols_cluster_robust",
]

CONTINUOUS_ESTIMATORS = {
    "naive_difference",
    "adjusted_ols",
    "adjusted_ols_omit_confounder",
    "adjusted_ols_naive_se",
    "adjusted_ols_cluster_robust",
    "ipw",
    "ipw_omit_confounder",
    "aipw",
    "aipw_ps_misspecified",
    "aipw_outcome_misspecified",
    "aipw_double_misspecified",
    "naive_difference_complete_case",
    "adjusted_ols_complete_case",
    "aipw_complete_case",
    "adjusted_ols_missingness_ipw",
    "adjusted_oracle_includes_U",
}
BINARY_ESTIMATORS = {
    "naive_risk_difference",
    "logistic_gcomp_risk_difference",
    "ipw_risk_difference",
    "aipw_risk_difference",
    "logistic_gcomp_complete_case",
    "adjusted_oracle_includes_U",
}
COUNT_ESTIMATORS = {
    "naive_rate_difference",
    "poisson_offset_gcomp_rate_difference",
    "ipw_rate_difference",
    "rate_gcomp_complete_case",
}
ESTIMATORS_BY_OUTCOME = {
    "continuous": CONTINUOUS_ESTIMATORS,
    "binary": BINARY_ESTIMATORS,
    "count": COUNT_ESTIMATORS,
}
MISSING_DATA_ESTIMATORS = {
    "naive_difference_complete_case",
    "adjusted_ols_complete_case",
    "aipw_complete_case",
    "adjusted_ols_missingness_ipw",
    "logistic_gcomp_complete_case",
    "rate_gcomp_complete_case",
}
CLUSTER_COMPARISON_ESTIMATORS = {
    "adjusted_ols_naive_se",
    "adjusted_ols_cluster_robust",
}


class CovariateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["continuous", "binary"]
    distribution: Literal["normal", "bernoulli"]
    mean: float | None = None
    sd: float | None = Field(default=None, gt=0)
    p: float | None = Field(default=None, ge=0, le=1)
    role: str = "prognostic"

    @model_validator(mode="after")
    def validate_distribution(self) -> "CovariateSpec":
        if self.type == "continuous":
            if self.distribution != "normal":
                raise ValueError("continuous covariates currently require distribution='normal'")
            if self.mean is None or self.sd is None:
                raise ValueError("normal covariates require mean and sd")
        if self.type == "binary":
            if self.distribution != "bernoulli":
                raise ValueError("binary covariates currently require distribution='bernoulli'")
            if self.p is None:
                raise ValueError("bernoulli covariates require p")
        return self


class TreatmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "A"
    type: Literal["binary"] = "binary"
    assignment: Literal["logistic", "randomized"]
    formula: dict[str, float] = Field(default_factory=lambda: {"intercept": 0.0})

    @field_validator("formula")
    @classmethod
    def formula_must_have_values(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            return {"intercept": 0.0}
        return value

    @model_validator(mode="after")
    def validate_randomized_formula(self) -> "TreatmentSpec":
        if self.assignment == "randomized":
            non_intercept_terms = set(self.formula) - {"intercept"}
            if non_intercept_terms:
                raise ValueError("randomized assignment only supports an intercept term")
        return self


class TreatmentEffectHeterogeneitySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    modifier: str | None = None
    coefficient: float = 0.0

    @model_validator(mode="after")
    def validate_modifier(self) -> "TreatmentEffectHeterogeneitySpec":
        if self.enabled and not self.modifier:
            raise ValueError("enabled treatment heterogeneity requires a modifier")
        return self


class ExposureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "exposure"
    distribution: Literal["lognormal"] = "lognormal"
    meanlog: float
    sdlog: float = Field(gt=0)
    scale: float = Field(default=1.0, gt=0)


class OverdispersionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    model: Literal["negative_binomial"] = "negative_binomial"
    theta: float = Field(default=5.0, gt=0)


class OutcomeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "Y"
    type: Literal["continuous", "binary", "count"] = "continuous"
    model: Literal["linear", "logistic", "poisson"] = "linear"
    exposure: ExposureSpec | None = None
    treatment_effect: float
    treatment_effect_heterogeneity: TreatmentEffectHeterogeneitySpec = Field(
        default_factory=TreatmentEffectHeterogeneitySpec
    )
    coefficients: dict[str, float]
    noise_sd: float | None = Field(default=1.0, gt=0)
    overdispersion: OverdispersionSpec = Field(default_factory=OverdispersionSpec)

    @model_validator(mode="after")
    def validate_outcome_model(self) -> "OutcomeSpec":
        if self.type == "continuous" and self.model != "linear":
            raise ValueError("continuous outcomes currently require model='linear'")
        if self.type == "binary" and self.model != "logistic":
            raise ValueError("binary outcomes currently require model='logistic'")
        if self.type == "count":
            if self.model != "poisson":
                raise ValueError("count outcomes currently require model='poisson'")
            if self.exposure is None:
                raise ValueError("count outcomes require an exposure specification")
        if self.type != "count" and self.exposure is not None:
            raise ValueError("exposure is only supported for count outcomes")
        if self.type != "count" and self.overdispersion.enabled:
            raise ValueError("overdispersion is only supported for count outcomes")
        return self


class EstimandSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["marginal_ATE", "marginal_risk_difference", "marginal_rate_difference"]
    contrast: str = "E[Y(1) - Y(0)]"
    primary: Literal[
        "mean_difference",
        "risk_difference",
        "risk_ratio",
        "odds_ratio",
        "rate_difference",
        "rate_ratio",
        "log_rate_ratio",
    ] = "mean_difference"


class UnobservedConfounderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    name: str = "U"
    distribution: Literal["normal"] = "normal"
    mean: float = 0.0
    sd: float = Field(default=1.0, gt=0)
    treatment_coefficient: float = 0.0
    outcome_coefficient: float = 0.0
    observed: bool = False


class MissingDataSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    target: str = "Y"
    mechanism: Literal["MCAR", "MAR", "MNAR"] = "MCAR"
    rate: float = Field(default=0.0, ge=0.0, le=1.0)
    formula: dict[str, float] = Field(default_factory=dict)
    apply_to: list[str] = Field(default_factory=lambda: ["Y"])
    missing_indicator_prefix: str = "R"


class ClusterRandomInterceptSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_sd: float | None = Field(default=None, gt=0)
    treatment_sd: float = Field(default=0.0, ge=0)


class ClusterLevelConfounderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    name: str = "Z_cluster"
    distribution: Literal["normal"] = "normal"
    mean: float = 0.0
    sd: float = Field(default=1.0, gt=0)
    treatment_coefficient: float = 0.0
    outcome_coefficient: float = 0.0


class ClusterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    cluster_id: str = "cluster_id"
    n_clusters: int = Field(default=1, gt=0)
    cluster_size: int = Field(default=1, gt=0)
    cluster_size_distribution: Literal["fixed"] = "fixed"
    icc: float | None = Field(default=None, ge=0.0, lt=1.0)
    random_intercept: ClusterRandomInterceptSpec = Field(default_factory=ClusterRandomInterceptSpec)
    cluster_level_confounder: ClusterLevelConfounderSpec = Field(
        default_factory=ClusterLevelConfounderSpec
    )


class DGPContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    name: str
    template: TemplateName
    sample_sizes: list[int] = Field(min_length=1)
    n_replications: int = Field(gt=0)
    seed: int = Field(ge=0)
    covariates: dict[str, CovariateSpec] = Field(min_length=1)
    treatment: TreatmentSpec
    outcome: OutcomeSpec
    estimand: EstimandSpec
    unobserved_confounder: UnobservedConfounderSpec = Field(
        default_factory=UnobservedConfounderSpec
    )
    missing_data: MissingDataSpec = Field(default_factory=MissingDataSpec)
    clusters: ClusterSpec = Field(default_factory=ClusterSpec)
    estimators: list[EstimatorName] = Field(min_length=1)

    @field_validator("schema_version")
    @classmethod
    def schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {value}")
        return value

    @field_validator("sample_sizes")
    @classmethod
    def sample_sizes_positive(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("sample_sizes must be positive")
        return values

    @model_validator(mode="after")
    def validate_references(self) -> "DGPContract":
        covariate_names = set(self.covariates)

        treatment_terms = set(self.treatment.formula) - {"intercept"}
        unknown_treatment_terms = treatment_terms - covariate_names
        if unknown_treatment_terms:
            raise ValueError(f"unknown treatment formula terms: {sorted(unknown_treatment_terms)}")

        outcome_terms = set(self.outcome.coefficients) - {"intercept"}
        unknown_outcome_terms = outcome_terms - covariate_names
        if unknown_outcome_terms:
            raise ValueError(f"unknown outcome coefficient terms: {sorted(unknown_outcome_terms)}")

        heterogeneity = self.outcome.treatment_effect_heterogeneity
        if heterogeneity.enabled and heterogeneity.modifier not in covariate_names:
            raise ValueError(f"unknown heterogeneity modifier: {heterogeneity.modifier}")

        if self.outcome.type == "binary" and self.estimand.primary == "mean_difference":
            self.estimand.primary = "risk_difference"
        if self.outcome.type == "count" and self.estimand.primary == "mean_difference":
            self.estimand.primary = "rate_difference"
        if self.outcome.type == "continuous" and self.estimand.primary != "mean_difference":
            raise ValueError(
                "continuous outcomes currently require estimand.primary='mean_difference'"
            )
        if self.outcome.type == "binary" and self.estimand.primary not in {
            "risk_difference",
            "risk_ratio",
            "odds_ratio",
        }:
            raise ValueError("binary outcomes require a risk or odds estimand primary")
        if self.outcome.type == "count" and self.estimand.primary not in {
            "rate_difference",
            "rate_ratio",
            "log_rate_ratio",
        }:
            raise ValueError("count outcomes require a rate estimand primary")

        clusters = self.clusters
        if clusters.enabled:
            if self.outcome.type != "continuous":
                raise ValueError("cluster support currently targets continuous outcomes")
            if clusters.cluster_id in covariate_names:
                raise ValueError("cluster_id cannot collide with a covariate name")
            cluster_confounder = clusters.cluster_level_confounder
            if cluster_confounder.enabled and cluster_confounder.name in covariate_names:
                raise ValueError("cluster-level confounder name cannot collide with a covariate")

        missing = self.missing_data
        if missing.enabled:
            if missing.target != self.outcome.name:
                raise ValueError("missing_data currently supports the outcome target only")
            if set(missing.apply_to) != {self.outcome.name}:
                raise ValueError(
                    "missing_data currently supports apply_to containing only the outcome"
                )
            allowed_missing_terms = covariate_names | {self.treatment.name, self.outcome.name}
            if self.unobserved_confounder.enabled:
                allowed_missing_terms.add(self.unobserved_confounder.name)
            missing_terms = set(missing.formula) - {"intercept"}
            unknown_missing_terms = missing_terms - allowed_missing_terms
            if unknown_missing_terms:
                raise ValueError(
                    f"unknown missingness formula terms: {sorted(unknown_missing_terms)}"
                )
            if missing.mechanism == "MAR":
                forbidden = {self.outcome.name, self.unobserved_confounder.name}
                leaking_terms = missing_terms & forbidden
                if leaking_terms:
                    raise ValueError(f"MAR missingness cannot depend on {sorted(leaking_terms)}")
            if missing.mechanism == "MCAR" and missing.formula:
                raise ValueError("MCAR missingness should not specify a formula")

        allowed_estimators = ESTIMATORS_BY_OUTCOME[self.outcome.type]
        for estimator in self.estimators:
            estimator_name = str(estimator)
            if estimator_name not in allowed_estimators:
                raise ValueError(
                    f"estimator {estimator_name!r} is incompatible with "
                    f"outcome.type={self.outcome.type!r}"
                )
            if estimator_name in MISSING_DATA_ESTIMATORS and not self.missing_data.enabled:
                raise ValueError(f"estimator {estimator_name!r} requires missing_data.enabled=True")
            if estimator_name in CLUSTER_COMPARISON_ESTIMATORS and not self.clusters.enabled:
                raise ValueError(f"estimator {estimator_name!r} requires clusters.enabled=True")
            if estimator_name == "adjusted_oracle_includes_U" and not (
                self.unobserved_confounder.enabled
            ):
                raise ValueError(
                    "estimator 'adjusted_oracle_includes_U' requires "
                    "unobserved_confounder.enabled=True"
                )

        return self
