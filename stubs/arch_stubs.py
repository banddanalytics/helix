"""Ground-truth arch (ARCH/GARCH) API stub."""

from __future__ import annotations

STUB: dict[str, dict[str, set[str]]] = {
    "arch": {
        "arch_model": {"y", "x", "mean", "lags", "vol", "p", "o", "q",
                       "power", "dist", "hold_back", "rescale"},
        "fit": {"update_freq", "disp", "starting_values", "cov_type",
                "show_warning", "first_obs", "last_obs", "tol", "options",
                "backcast"},
        "forecast": {"horizon", "start", "align", "method", "simulations",
                     "rng", "random_state", "reindex"},
        "params": set(),
        "resid": set(),
        "conditional_volatility": set(),
        "summary": set(),
        "plot": {"annualize", "scale", "fig"},
        "hedgehog_plot": {"burn", "data_plot", "volatility_plot"},
        "ConstantMean": {"y", "hold_back", "volatility", "distribution"},
        "ARX": {"y", "x", "lags", "constant", "hold_back",
                "volatility", "distribution", "rescale"},
        "GARCH": {"p", "o", "q", "power"},
        "EGARCH": {"p", "o", "q"},
        "FIGARCH": {"p", "q", "power", "truncation"},
        "Normal": set(),
        "StudentsT": set(),
        "SkewStudent": set(),
        "GeneralizedError": set(),
    }
}
