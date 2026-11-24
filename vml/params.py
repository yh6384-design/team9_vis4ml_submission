"""Every number we chose, in one place. Change a value here, never inside a stage script.

If you change anything after results are shared, say so in the commit message, because
the five flagged groups and the Experiment 2 numbers depend on these values.
"""

SEED = 20261119

# ---------------------------------------------------------------- data and cohort
BLOCKS = ("train", "dev", "test")               # from cohort/code/build_cohort.py (2008-13, 2014, 2015-17)
CONFIRMED_SHARE_MIN = 0.80                      # a block below 80% confirmed is descriptive only
DEV_SPLIT = "halves"                            # dev families split into disjoint slice-search / assessment halves
DEV_SEARCH_FRACTION = 0.5                       # set DEV_SPLIT = "none" to search on all of dev
ROUND_CAP = 3                                   # rounds 3, 4, ... are grouped as "r3+"

# ---------------------------------------------------------------- examiner profile
PROFILE_POOL_VERIFIED_ONLY = True               # history uses only reference episodes with a verified examiner
LAMBDA_GRID = (0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)   # shrinkage strength,
                                                # tuned together with the LR C by forward validation inside train
AU_PRIOR_KAPPA = 20                             # the art-unit rate itself shrinks toward the global rate known at t
FORWARD_VAL_YEARS = (2011, 2012, 2013)          # validation years inside the training block (family-purged)
TIER_MIN_DEV_FAMILIES = 100                     # history tiers are merged until each has >= 100 dev families

# ---------------------------------------------------------------- examiner groups (dashboard filter only, not a model input)
# ONE group per examiner, the same on every row, from the examiner's decisions mailed before EXGROUP_CUTOFF (= all training and
# dev years). Group = allowance rate in those decisions, cut at the quintiles of the examiners' rates (examiners with
# >= EXGROUP_MIN_N decisions): G1 = lowest ... G5 = highest; G0 = fewer than EXGROUP_MIN_N decisions before the cutoff.
# Not used in any model, measure, experiment or in the flagging procedure.
EXGROUP_CUTOFF = "2015-01-01"
EXGROUP_K = 5
EXGROUP_MIN_N = 5
EXAMINER_MIN_FREQ = 5                           # LR, profile on: examiners with < 5 training rows share one "rare" column

# ---------------------------------------------------------------- models (same grid size for profile off/on)
LR_GRID = ({"C": 0.001}, {"C": 0.01}, {"C": 0.1}, {"C": 1.0})
GBT_GRID = ({"max_depth": 2, "learning_rate": 0.05}, {"max_depth": 3, "learning_rate": 0.05},
            {"max_depth": 2, "learning_rate": 0.1}, {"max_depth": 3, "learning_rate": 0.1})
GBT_FIXED = {"max_iter": 200, "min_samples_leaf": 20, "l2_regularization": 1.0}
ART_UNIT_MIN_FREQ = 30                          # rarer art units are pooled as "infrequent" in the LR one-hot
LEARNED_MODELS = ("lr_off", "lr_on", "gbt_off", "gbt_on")
ALL_MODELS = ("base",) + LEARNED_MODELS
MODEL_LABEL = {"base": "Base rate", "lr_off": "LR, profile off", "lr_on": "LR, profile on",
               "gbt_off": "Trees, profile off", "gbt_on": "Trees, profile on"}
MODEL_SHORT = {"base": "Base", "lr_off": "LR off", "lr_on": "LR on", "gbt_off": "Trees off", "gbt_on": "Trees on"}
PAIRS = (("lr_off", "lr_on"), ("gbt_off", "gbt_on"))

# ---------------------------------------------------------------- calibration measurement
CLIP = 1e-6                                     # probabilities clipped to [1e-6, 1-1e-6] for log loss
N_BINS = 10                                     # ten fixed-width bins
SENS_BINS = (5, 15)                             # five- and fifteen-bin sensitivity checks
BOOT_B = 1000                                   # family bootstrap resamples for reported intervals
CI = 0.95
EBM_MAX_BINS = 256                              # learned curve: same EBM settings as pycalibrate
EBM_CROSSFIT_FOLDS = 5                          # family-grouped cross-fitting
CURVE_GRID = 101

# ---------------------------------------------------------------- slices
SLICE_MAX_PREDICATES = 2
SLICE_MIN_FAMILIES = 100                        # in discovery AND in assessment
SLICE_EFFECT_MIN = 0.05                         # |slice gap - overall gap| must be at least 5 points ...
SLICE_BOOT_B = 500                              # ... and its family-bootstrap 95% interval must exclude 0
SLICE_TOP_K = 5                                 # top five = flagged groups ⚑1-⚑5, chosen by a fixed rule on 2014 part A
VIEW_MIN_CASES = 30                             # Visualization 1: a row with fewer cases is gray ("few cases, look one row down")
RESIDUAL_TREE_DEPTH = 2
RESIDUAL_TREE_MIN_LEAF = 60                     # checkpoints per leaf (leaves still need 100 families to be eligible;
                                                # with ~470 search rows a 100-row leaf rarely allows a second split)
SLICE_ATTRS = ("tc", "art_unit", "hist_tier", "round_c", "rce", "prior_type",
               "g101", "g102", "g103", "g112", "g_dp")        # case features; not examiner group (it contains the 2014
                                                                  # outcomes the search is done on) and not examiner id /
                                                                  # filing year (too few cases per value)

# ---------------------------------------------------------------- Experiment 3 (practice copy with a known answer)
E3_BASE_MODEL = "lr_off"                        # q(X) = this model's real dev predictions
E3_SHIFTS = (0.25, 0.5, 1.0)                    # planted distortion, on the logit scale, both signs
E3_SEEDS = 20                                   # repeats per planted scenario
E3_NULL_SEEDS = 50                              # undistorted controls
E3_BOOT_B = 200
E3_HIT_JACCARD = 0.5                            # a top-5 slice "finds" the planted one if membership overlap >= 0.5
