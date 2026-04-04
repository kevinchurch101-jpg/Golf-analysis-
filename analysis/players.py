"""
Fairway Intel — Player Database
Complete player profiles from Section 7 of Kevin's Framework.
As of April 2026 — update continuously.
Designation, distance, price flags, course triggers all encoded here.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Designation codes
EC_PLUS  = "EXTRA_CONFIRM_PLUS"
FWRK     = "FRAMEWORK"
EC_MINUS = "EXTRA_CONFIRM_MINUS"
FALLEN   = "FALLEN_STAR"

# Distance tiers
ELITE    = "ELITE_BOMBER"
ABOVE    = "ABOVE_AVERAGE"
AVG      = "AVERAGE"
SHORT    = "SHORT"


@dataclass
class PlayerProfile:
    name: str
    designation: str
    distance_tier: str
    kevin_notes: str
    price_flags: List[str] = field(default_factory=list)
    course_triggers: List[str] = field(default_factory=list)
    pool_eligible: bool = True
    pool_notes: str = ""
    frl_target: bool = False
    specialist_courses: List[str] = field(default_factory=list)
    auto_price_trigger: Optional[int] = None          # Min American odds for auto-consider
    max_price_threshold: Optional[int] = None         # Never back above this (American)
    shot_shape_preference: Optional[str] = None       # "draw", "fade", "high_cut", None
    is_liv: bool = False
    augusta_notes: str = ""

    @property
    def designation_label(self) -> str:
        labels = {
            EC_PLUS:  "EXTRA CONFIRM +",
            FWRK:     "FRAMEWORK",
            EC_MINUS: "EXTRA CONFIRM -",
            FALLEN:   "FALLEN STAR",
        }
        return labels.get(self.designation, self.designation)


# ──────────────────────────────────────────────────────────────
# PLAYER DATABASE
# ──────────────────────────────────────────────────────────────

PLAYER_DB: List[PlayerProfile] = [

    PlayerProfile(
        name="Scottie Scheffler",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Will return to elite form. Best player in world when on. No price flags — always short enough to require framework support.",
        pool_notes="Deploy at Signatures and Majors only.",
        augusta_notes="Elite across all Augusta categories. Distance on par-5s. Course management elite.",
    ),

    PlayerProfile(
        name="Rory McIlroy",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Elite OTT, strong APP. Framework assessment fully.",
        pool_notes="Deploy at Signatures and Majors only.",
        augusta_notes="Elite OTT on par-5s. Draw bias natural. Multiple runner-up finishes.",
    ),

    PlayerProfile(
        name="Xander Schauffele",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Will return to elite form. Eye him at valuable odds when available.",
        pool_notes="Deploy at Signatures.",
        augusta_notes="Consistent Augusta performer. Elite ball-striker.",
    ),

    PlayerProfile(
        name="Jon Rahm",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Still elite in tournaments he plays. LIV — limited PGA starts. Monitor if he gets beneficial odds at events he enters.",
        is_liv=True,
        pool_notes="LIV player — eligible only 4 PGA events/year. Strategic deploy.",
        augusta_notes="Masters champion. Draw ball. Elite all-around.",
    ),

    PlayerProfile(
        name="Collin Morikawa",
        designation=EC_PLUS, distance_tier=AVG,
        kevin_notes="First name on card at approach-dominant accuracy courses when healthy. Has random bad stretches — acknowledge this risk. Lower value at courses with high ARG emphasis. APP 0.954, elite accuracy. Efficient shorter hitter archetype.",
        course_triggers=["approach_dominant", "accuracy_premium"],
        price_flags=["auto_trigger_approach_dominant_accuracy_courses"],
        pool_notes="Deploy at approach-dominant Signatures.",
        augusta_notes="Elite approach from any yardage. Shorter distance limits par-5 edge.",
    ),

    PlayerProfile(
        name="Tommy Fleetwood",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Concerns about ability to win. No PGA full-field win. One-bad-round syndrome per Pat Mayo. Positions only unless framework strongly supports outright.",
        price_flags=["positions_only_default"],
        pool_notes="Avoid for pool — win equity concern.",
    ),

    PlayerProfile(
        name="Ludvig Åberg",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Framework assessment. Blew 3-shot Players lead 2026. Elite overall profile — watch closing ability development.",
        pool_notes="Deploy when form and course fit align.",
        augusta_notes="Elite ball-striker. Debut or limited Augusta experience — apply newcomer discount.",
    ),

    PlayerProfile(
        name="Russell Henley",
        designation=EC_PLUS, distance_tier=SHORT,
        kevin_notes="Good player — market consistently overvalues him at short prices. At the RIGHT longer price he becomes genuinely interesting. The concern is purely valuation not ability. Fade sub-20/1. Intriguing at 30/1+ when course fits.",
        auto_price_trigger=3000,       # 30/1
        price_flags=["fade_below_20_1", "intriguing_30_1_plus"],
        pool_notes="Pool eligible when approach-dominant events align.",
    ),

    PlayerProfile(
        name="Hideki Matsuyama",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Doesn't need form going into tournaments to turn it around. Can win with irons and around-green play specifically. Best ARG on Tour. Masters winner. Don't require sustained form window. Apply slightly different form threshold.",
        course_triggers=["arg_premium"],
        pool_notes="Deploy at Augusta and ARG-friendly Signatures.",
        augusta_notes="Masters champion. Elite ARG — course-specific putting history positive. Knows where to miss on every hole.",
    ),

    PlayerProfile(
        name="Robert MacIntyre",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Plays well in tough conditions and hard courses. Not afraid of big events — performs under pressure. Elite putter. APP structural concern at approach-dominant courses. Upgrade consideration at tough demanding setups.",
        course_triggers=["tough_conditions", "demanding_setup"],
        pool_notes="Consider at Signatures with tough setups.",
    ),

    PlayerProfile(
        name="Min Woo Lee",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Framework assessment. Elite overall profile.",
        pool_notes="Developing pool option.",
    ),

    PlayerProfile(
        name="Sepp Straka",
        designation=EC_PLUS, distance_tier=AVG,
        kevin_notes="High win equity in any field where irons are emphasized. Oddsmakers now treating him more as contender — value compressed. PRICE TRIGGERS: Must consider at 45/1. Must consider at 30/1 in weak fields. Wind player. Honda 2022 winner.",
        auto_price_trigger=4500,       # 45/1
        price_flags=["must_consider_45_1", "must_consider_30_1_weak_field"],
        course_triggers=["irons_emphasis", "wind_conditions"],
        pool_notes="Pool eligible in weak field events.",
    ),

    PlayerProfile(
        name="Matt McCarty",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Won Cognizant 2026. Framework assessment.",
        pool_notes="Pool eligible — recent win equity established.",
    ),

    PlayerProfile(
        name="Maverick McNealy",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="T3 Valero 2025. Balanced all-around profile. No PGA win equity.",
        price_flags=["no_win_equity_positions_preferred"],
    ),

    PlayerProfile(
        name="Si Woo Kim",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Currently playing above normal level but been very consistent. Needs spike putting from earlier in career to win. Kevin hasn't loved recent odds — they have adjusted to his form. Flag when value returns. Career spike putter. Technical swing fix confirmed 2026.",
        price_flags=["value_compressed_monitor_odds_drift"],
    ),

    PlayerProfile(
        name="Jordan Spieth",
        designation=EC_PLUS, distance_tier=ABOVE,
        kevin_notes="Like his form at Texas venues. Pool value at right events. Never bet sub-20/1 given OTT weakness and volatility. Pool trigger: Texas/Colonial venues when trending. Volatile driver but veteran closer.",
        max_price_threshold=2000,      # Never below 20/1 American (avoid sub-20/1)
        course_triggers=["texas_venues", "colonial"],
        specialist_courses=["Colonial Country Club", "Texas venues"],
        pool_notes="Deploy at Colonial and Texas venues. Pool value.",
        augusta_notes="Draw ball. Multiple Augusta contention finishes. Veteran closer. OTT liability on tight Augusta holes.",
    ),

    PlayerProfile(
        name="Patrick Cantlay",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Seems to have lost top level game — monitor for return. Peak is high when on. Nicklaus design specialist. Need current form evidence before backing at any price.",
        course_triggers=["nicklaus_design"],
        specialist_courses=["Muirfield Village", "Nicklaus-design courses"],
        pool_notes="Reserve for Nicklaus-design events when form returns.",
    ),

    PlayerProfile(
        name="Rickie Fowler",
        designation=EC_MINUS, distance_tier=ABOVE,
        kevin_notes="Very much overrated. Do not trust at recent odds. Career APP 0.242 ceiling concern. Only at 40/1+ when APP genuinely spiking above 0.300. Even then needs extra confirmation given general skepticism.",
        auto_price_trigger=4000,       # 40/1 minimum
        price_flags=["extra_skepticism_always", "app_must_spike_0300"],
    ),

    PlayerProfile(
        name="Tony Finau",
        designation=FALLEN, distance_tier=ELITE,
        kevin_notes="Waiting to see if he finds his old form. OTT negative at long accurate courses. At 100/1+ with any form return: immediately intriguing. Was genuinely elite — decline has identifiable causes.",
        auto_price_trigger=10000,      # 100/1
        price_flags=["fallen_star_100_1_trigger"],
        augusta_notes="Elite distance a factor on par-5s. OTT accuracy at Augusta — watchlist.",
    ),

    PlayerProfile(
        name="Brian Harman",
        designation=EC_MINUS, distance_tier=SHORT,
        kevin_notes="Don't love his lack of distance. Defending Valero via extreme wind spike anomaly — APP 0.138 career. Needs specific wind/conditions setup to be relevant. Extra skepticism required before backing.",
        course_triggers=["extreme_wind", "short_course"],
        price_flags=["needs_wind_anomaly", "app_career_liability"],
    ),

    PlayerProfile(
        name="Cameron Young",
        designation=EC_PLUS, distance_tier=ELITE,
        kevin_notes="Really love his game. Trending towards elite player. KEY UPDATE: Has greatly improved his putting in last year with his caddy — factor this into his overall profile assessment. Elite OTT, strong APP. Back him when framework supports. Lower threshold to pull trigger.",
        pool_notes="Deploy when approach-dominant Signatures align.",
        augusta_notes="Elite distance on par-5s. Improved putting changes Augusta profile meaningfully.",
    ),

    PlayerProfile(
        name="Will Zalatoris",
        designation=FALLEN, distance_tier=ABOVE,
        kevin_notes="My guy — independent belief in talent. Putting remains a concern but upside ceiling is real. Right course type: modest winning score + irons dominant. At 100/1+ with any signs of life: immediately intriguing. At 70/1 in bad form: not tasty. Not ready Valero 2026 (injury return, MC Houston).",
        auto_price_trigger=10000,
        price_flags=["fallen_star_100_1_trigger", "70_1_bad_form_not_enough"],
        course_triggers=["irons_dominant", "modest_winning_score"],
        augusta_notes="Improved putting profile (caddy influence 2025). Irons elite when healthy. Multiple Masters contention finishes. Watch injury return timeline.",
    ),

    PlayerProfile(
        name="Ryo Hisatsune",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Negative 200+ bucket — weakness at longest approach distance. 8 straight cuts. T5 Valero 2025.",
        price_flags=["long_approach_bucket_weakness"],
    ),

    PlayerProfile(
        name="Denny McCarthy",
        designation=EC_PLUS, distance_tier=SHORT,
        kevin_notes="Framework trigger: elite career putter (0.414) + APP spiking = back him. Runner-up Valero 2024. 3rd most SG at this course since 2016. Trigger when APP spiking above career mean.",
        course_triggers=["valero_texas_open"],
        price_flags=["mcccarthy_trigger_app_spiking_elite_putter"],
        frl_target=True,
    ),

    PlayerProfile(
        name="Kristoffer Reitan",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="APP negative — distance doesn't convert. Not a fit at approach courses.",
        price_flags=["distance_doesnt_convert_approach_courses"],
    ),

    PlayerProfile(
        name="Nick Taylor",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Course specialist at Scottsdale and Canada — potentially others. Monitor for emerging specialist patterns at other venues. 2026 form poor. OTT negative. Specialist trigger only.",
        specialist_courses=["TPC Scottsdale", "Hamilton Golf Club"],
        course_triggers=["scottsdale", "canada_open"],
        pool_notes="Specialist trigger events only.",
    ),

    PlayerProfile(
        name="Alex Noren",
        designation=FWRK, distance_tier=SHORT,
        kevin_notes="Just can't win stateside — question his upside in PGA Tour events. Elite putter. OTT liability at long courses. European Tour success doesn't translate consistently.",
        price_flags=["stateside_win_concern"],
    ),

    PlayerProfile(
        name="Thorbjorn Olesen",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="DP World Tour win equity. Framework assessment.",
    ),

    PlayerProfile(
        name="Austin Smotherman",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Conners/Spaun archetype. KFT 2x winner 2025. Houston WD = baby birth not form. Valspar MC same reason.",
    ),

    PlayerProfile(
        name="Rico Hoey",
        designation=EC_PLUS, distance_tier=ELITE,
        kevin_notes="Recurring FRL target weekly at approach-heavy venues. Spike putter with great ball striking in 2025. Hoping to see return in 2026 but struggling early. Odds haven't gotten better which is a concern for value. EXTRA CONFIRM + because believe in the upside returning. FRL only — never outright at this level.",
        frl_target=True,
        price_flags=["frl_only_never_outright", "odds_value_monitor"],
        course_triggers=["approach_heavy"],
    ),

    PlayerProfile(
        name="Jordan Smith",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Debut concern at new venues. Framework assessment.",
        price_flags=["debut_discount_new_venues"],
    ),

    PlayerProfile(
        name="Keith Mitchell",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Past his window at compressed odds. OTT genuinely good. Only at 50/1+.",
        auto_price_trigger=5000,
        price_flags=["only_50_1_plus"],
    ),

    PlayerProfile(
        name="Sudarshan Yellamaraju",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Insufficient Tour rounds for full DG rating. Hot 2026 form.",
    ),

    PlayerProfile(
        name="Marco Penge",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Accuracy-dependent bomber — reassess weekly by course fit. Up and coming — monitor development trajectory. Live at forgiving courses with spiking irons.",
        course_triggers=["forgiving_course", "spiking_irons"],
        price_flags=["reassess_weekly_course_fit"],
    ),

    PlayerProfile(
        name="Webb Simpson",
        designation=FWRK, distance_tier=SHORT,
        kevin_notes="Harbour Town positional golf course type specialist. Specialist trigger RBC Heritage only. Past window everywhere else.",
        specialist_courses=["Harbour Town Golf Links"],
        course_triggers=["rbc_heritage", "harbour_town"],
        pool_notes="Deploy at Harbour Town only.",
    ),

    PlayerProfile(
        name="Max McGreevy",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Bronson Burgoon",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Elite OTT. FRL consideration only at huge prices.",
        frl_target=True,
        price_flags=["frl_only_huge_prices"],
    ),

    PlayerProfile(
        name="Johnny Keefer",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Framework assessment. Home course TPC SA advantage noted.",
        course_triggers=["tpc_san_antonio"],
    ),

    PlayerProfile(
        name="William Mouw",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Total driving elite. Lottery only at right price.",
        price_flags=["lottery_only_right_price"],
    ),

    PlayerProfile(
        name="Austin Eckroat",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Davis Thompson",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Tom Kim",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Needs to find accuracy off tee again before considering. Multiple PGA wins — win equity exists when accurate.",
        price_flags=["accuracy_must_return_before_backing"],
    ),

    PlayerProfile(
        name="Billy Horschel",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="3 historic Valero top-5s. Post-surgery concern 2026.",
        course_triggers=["valero_texas_open"],
    ),

    PlayerProfile(
        name="Bud Cauley",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Joel Dahmen",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Accurate driver. Framework assessment.",
    ),

    PlayerProfile(
        name="Andrew Novak",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Extreme putter volatility. Negative 200+ bucket. FRL consideration at long prices only.",
        frl_target=True,
        price_flags=["frl_only_long_prices", "negative_200_plus_bucket"],
    ),

    PlayerProfile(
        name="J.T. Poston",
        designation=FWRK, distance_tier=SHORT,
        kevin_notes="Short courses favor him specifically. Can really putt. Accurate driver. APP modest. Flag at short accurate courses with putting premium.",
        course_triggers=["short_course", "putting_premium"],
    ),

    PlayerProfile(
        name="Alex Smalley",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Christiaan Bezuidenhout",
        designation=FWRK, distance_tier=SHORT,
        kevin_notes="OTT liability at long courses. Framework assessment.",
        price_flags=["ott_liability_long_courses"],
    ),

    PlayerProfile(
        name="Beau Hossler",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Elite putter — poor ball-striking. Profile mismatch at approach courses.",
        price_flags=["profile_mismatch_approach_courses"],
    ),

    PlayerProfile(
        name="Eric Cole",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="OTT negative. Framework assessment.",
        price_flags=["ott_negative"],
    ),

    PlayerProfile(
        name="Chad Ramey",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Losing approach at approach-dominant courses.",
        price_flags=["app_losing_approach_dominant"],
    ),

    PlayerProfile(
        name="Matt Wallace",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment. Elite T2G week Valero 2021 noted.",
    ),

    PlayerProfile(
        name="Mackenzie Hughes",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Great putter. Gaining distance off tee — positive trajectory. Knows how to scramble and game a course — course management strength. Monitor as distance improvement continues.",
        course_triggers=["course_management_premium"],
    ),

    PlayerProfile(
        name="Mac Meissner",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Very solid ball striker to watch. Flag when framework supports.",
    ),

    PlayerProfile(
        name="Lee Hodges",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="T6 Valero 2023 elite ball-striking. Rib injury 2026.",
        price_flags=["injury_concern_2026"],
    ),

    PlayerProfile(
        name="Haotong Li",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Sami Välimäki",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Wind experience. OTT liability. Framework assessment.",
        course_triggers=["wind_conditions"],
    ),

    PlayerProfile(
        name="Andrew Putnam",
        designation=FWRK, distance_tier=SHORT,
        kevin_notes="ARG elite. OTT terrible. Framework assessment.",
        price_flags=["ott_terrible_limits_ceiling"],
    ),

    PlayerProfile(
        name="Seamus Power",
        designation=FWRK, distance_tier=SHORT,
        kevin_notes="Tour average across all categories.",
    ),

    PlayerProfile(
        name="Doug Ghim",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Jhonattan Vegas",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="FRL consideration — hits far and putts well sometimes. Flag for FRL at right venues and conditions.",
        frl_target=True,
    ),

    PlayerProfile(
        name="Chris Kirk",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Strong historic Valero record. Form declining.",
        course_triggers=["valero_texas_open"],
    ),

    PlayerProfile(
        name="Bryson DeChambeau",
        designation=EC_PLUS, distance_tier=ELITE,
        kevin_notes="Elite distance — back at bombers courses and universally penal setups. KEY NOTE: Underrated elite putter — factor this in always. Has to consider if he can overpower every course he plays. LIV — limited PGA starts. Winged Foot principle applies.",
        is_liv=True,
        course_triggers=["bombers_course", "universally_penal"],
        price_flags=["liv_limited_starts", "elite_putter_factor_always"],
        pool_notes="LIV player — eligible only 4 PGA events/year. Strategic deploy.",
        augusta_notes="Elite putter + distance on par-5s = genuine Augusta threat. Winged Foot principle — can overpower. LIV experience with major prep.",
    ),

    PlayerProfile(
        name="Sam Burns",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Want to believe he gets back to better self. Elite putter — McCarthy tier trigger when ball-striking spikes. Monitor for form return.",
        course_triggers=["app_spiking"],
        price_flags=["mcccarthy_tier_trigger_when_irons_spike"],
    ),

    PlayerProfile(
        name="Wyndham Clark",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Believe he will turn it around soon. KEY NOTE: Likes to play high cuts — track shot shape requirements weekly. US Open winner 2023. Framework assessment with shot shape consideration.",
        shot_shape_preference="high_cut",
        price_flags=["track_shot_shape_requirements_weekly"],
        augusta_notes="High cut preference — Augusta draw bias is a real concern. Monitor hole-by-hole fit.",
    ),

    PlayerProfile(
        name="Viktor Hovland",
        designation=FALLEN, distance_tier=ABOVE,
        kevin_notes="Believe he will turn it around but volatile and unpredictable. AUTO CONSIDER AT 40/1 OR LONGER — price trigger built in. Was genuinely elite. Decline has identifiable causes. APP strong, OTT modest.",
        auto_price_trigger=4000,
        price_flags=["fallen_star_auto_consider_40_1"],
        pool_notes="Auto-consider pool at 40/1+ when form returns.",
        augusta_notes="Elite ball-striker when on. Volatility is the risk.",
    ),

    PlayerProfile(
        name="Justin Thomas",
        designation=FALLEN, distance_tier=ABOVE,
        kevin_notes="Believe he will turn it around but volatile and unpredictable. AUTO CONSIDER AT 40/1 OR LONGER — same trigger as Hovland. 2x major winner. Win equity remains high if healthy. OTT modest but short game elite.",
        auto_price_trigger=4000,
        price_flags=["fallen_star_auto_consider_40_1"],
        pool_notes="Deploy when form and price align.",
        augusta_notes="Short game elite at Augusta. Major winner — experience edge. Needs form return.",
    ),

    PlayerProfile(
        name="Shane Lowry",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Value in approach-heavy courses, wind, and weaker fields specifically. Open champion — wind player. Flag at windy approach courses.",
        course_triggers=["wind_conditions", "approach_heavy", "weak_field"],
        augusta_notes="Windy Augusta editions suit him. OTT modest but solid all-around.",
    ),

    PlayerProfile(
        name="Keegan Bradley",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Corey Conners",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Struggles with putting but great consistent ball striker. 2x Valero winner — template for ball-striker archetype. Course fit trigger at ball-striker venues.",
        course_triggers=["ball_striker_venue", "valero_texas_open"],
        specialist_courses=["TPC San Antonio"],
    ),

    PlayerProfile(
        name="Patrick Reed",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Gamer who knows how to compete especially at Augusta. Likely underrated with move to LIV — not sure on current win equity. Augusta-specific: gamer mentality and course knowledge matter here. Monitor LIV performance for current form assessment.",
        is_liv=True,
        course_triggers=["augusta"],
        pool_notes="LIV player — Augusta pool consideration.",
        augusta_notes="Gamer mentality. Deep Augusta knowledge. Course management elite. Masters champion — knows how to win here. Monitor current form.",
    ),

    PlayerProfile(
        name="Lucas Glover",
        designation=FWRK, distance_tier=SHORT,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Adam Scott",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Veteran — still relevant at right courses.",
        augusta_notes="Augusta specialist historically. Draw ball. Course management veteran.",
    ),

    PlayerProfile(
        name="Sungjae Im",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Harris English",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Elite putter. Framework assessment.",
    ),

    PlayerProfile(
        name="Taylor Moore",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Adrien Dumont de Chassart",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Young bomber — watch development trajectory.",
    ),

    PlayerProfile(
        name="Taylor Pendrith",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Elite OTT. APP modest. Distance converts when accurate.",
        price_flags=["distance_converts_when_accurate"],
    ),

    PlayerProfile(
        name="Nick Dunlap",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Young talent. OTT negative concern. Developing.",
        price_flags=["ott_negative_developing"],
    ),

    PlayerProfile(
        name="Michael Thorbjornsen",
        designation=EC_PLUS, distance_tier=ELITE,
        kevin_notes="Up and comer — Kevin is keeping eye on development. Only at bombers courses 50/1+. Changed from EXTRA CONFIRM - to EXTRA CONFIRM + based on trajectory. Distance useless at penal accurate courses. Worst Sunday scoring average on Tour — flag this always.",
        auto_price_trigger=5000,
        price_flags=["bombers_courses_only", "worst_sunday_scoring_average_flag"],
        course_triggers=["bombers_course"],
    ),

    PlayerProfile(
        name="Gordon Sargent",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="APP negative — distance doesn't convert yet. Developing.",
        price_flags=["app_negative_developing"],
    ),

    PlayerProfile(
        name="Luke Clanton",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Developing Tour player. Framework assessment.",
    ),

    PlayerProfile(
        name="Davis Riley",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Tom Hoge",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="OTT terrible. Short hitter. Framework assessment.",
        price_flags=["ott_terrible_short"],
    ),

    PlayerProfile(
        name="Neal Shipley",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Kevin Roy",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Akshay Bhatia",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Elite accuracy and good approach play. Up and coming. Monitor for value — lacks distance which limits ceiling at some venues. Won Valero 2024. Young talent with real win equity developing.",
        course_triggers=["accuracy_premium", "valero_texas_open"],
    ),

    PlayerProfile(
        name="Jake Knapp",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Elite putter. OTT strong. Framework assessment.",
    ),

    PlayerProfile(
        name="Stephan Jaeger",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="APP weak at approach-dominant courses.",
        price_flags=["app_weak_approach_courses"],
    ),

    PlayerProfile(
        name="Max Greyserman",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Big hitter. ACC negative. Framework assessment.",
        price_flags=["accuracy_negative"],
    ),

    PlayerProfile(
        name="Ben Griffin",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Solid all-around profile. Framework assessment.",
    ),

    PlayerProfile(
        name="Taylor Montgomery",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="OTT negative. Below average driver.",
        price_flags=["ott_negative"],
    ),

    PlayerProfile(
        name="Nicolai Højgaard",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Great ball striker who has improved on PGA Tour after DP World Tour success. European Tour wins. Development trajectory positive.",
    ),

    PlayerProfile(
        name="Rasmus Højgaard",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Great ball striker who has improved on PGA Tour after DP World Tour success. DP World Tour wins. Monitor continued development.",
    ),

    PlayerProfile(
        name="Santiago De La Torre",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Austin Cook",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Patrick Fishburn",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Chris Gotterup",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Monitor for value. Has won twice this year — real win equity now established. Big hitter developing Tour player. Win equity changes the calculus.",
    ),

    PlayerProfile(
        name="Jason Day",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="ARG elite. Veteran. Framework assessment.",
        augusta_notes="ARG elite. Veteran Augusta experience. Draw ball natural.",
    ),

    PlayerProfile(
        name="Sahith Theegala",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Crafty creative player — monitor for return to form. Multiple runner-up finishes — close but no win yet. When form returns, creative course management is a genuine edge.",
        price_flags=["no_win_equity_yet", "course_management_edge_when_on"],
    ),

    PlayerProfile(
        name="Kurt Kitayama",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="APP strong. OTT elite. Putting negative.",
        price_flags=["putting_negative_upside_only"],
    ),

    PlayerProfile(
        name="Harris Nesmith",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Young bomber on KFT/PGA bubble. Watch development.",
    ),

    PlayerProfile(
        name="Garrick Higgo",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="DP World Tour win. Inconsistent. Framework assessment.",
    ),

    PlayerProfile(
        name="Andrew Landry",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Won Valero 2018 — form long gone.",
        price_flags=["form_long_gone"],
    ),

    PlayerProfile(
        name="Brice Garnett",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="David Skinns",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Hayden Buckley",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Martin Trainer",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Harry Hall",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Elite putter. APP weak. Framework assessment.",
        price_flags=["app_weak_putter_mismatch"],
    ),

    PlayerProfile(
        name="Carl Yuan",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),

    PlayerProfile(
        name="Ryan Gerard",
        designation=FWRK, distance_tier=ABOVE,
        kevin_notes="APP strong. Watch development trajectory.",
    ),

    PlayerProfile(
        name="Sam Stevens",
        designation=FWRK, distance_tier=ELITE,
        kevin_notes="Young bomber developing. Framework assessment.",
    ),

    PlayerProfile(
        name="Patrick Flavin",
        designation=FWRK, distance_tier=AVG,
        kevin_notes="Framework assessment.",
    ),
]


# ──────────────────────────────────────────────────────────────
# LOOKUP HELPERS
# ──────────────────────────────────────────────────────────────

_DB_INDEX: Dict[str, PlayerProfile] = {p.name.lower(): p for p in PLAYER_DB}


def get_player(name: str) -> Optional[PlayerProfile]:
    """Look up a player by name (case-insensitive, partial match fallback)."""
    key = name.lower().strip()
    if key in _DB_INDEX:
        return _DB_INDEX[key]
    # Partial last-name match
    for db_name, profile in _DB_INDEX.items():
        if key in db_name or db_name.split()[-1] in key:
            return profile
    return None


def get_players_by_designation(designation: str) -> List[PlayerProfile]:
    return [p for p in PLAYER_DB if p.designation == designation]


def get_frl_targets() -> List[PlayerProfile]:
    return [p for p in PLAYER_DB if p.frl_target]


def get_specialists() -> List[PlayerProfile]:
    return [p for p in PLAYER_DB if p.specialist_courses]


def get_liv_players() -> List[PlayerProfile]:
    return [p for p in PLAYER_DB if p.is_liv]


def get_auto_trigger_players(american_odds: int) -> List[PlayerProfile]:
    """Return players whose auto_price_trigger is met by the given American odds."""
    result = []
    for p in PLAYER_DB:
        if p.auto_price_trigger and american_odds >= p.auto_price_trigger:
            result.append(p)
    return result
