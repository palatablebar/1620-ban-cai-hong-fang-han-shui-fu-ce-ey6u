from .stack_cards.contracts import Field

EXPOSURE_UNIT = '未复测预估含水超限百分点'
TITLE = '板材烘房含水复测'
ROLE = '板材厂质检与烘房班长'
OBJECT = '烘房层位单'
TARGET = '下线含水率'
ALGORITHM = 'CART 回归树'
MODE = 'regression'
IS_SURVIVAL = False
MODEL_EPOCH = 'kilnboard-1.0'
REGIONS = ('烘房东舱', '烘房西舱', '返工隔舱')
SIGNAL_NAMES = ('moisture_loading', 'residence_per_mm', 'steam_penetration', 'stack_shadow', 'vent_effect')
RAW_EXPLAIN_INDEX = (None, None, None, None, None)
RESOURCE = '复测班组半小时'
DEFAULT_BUDGET = 16
ACTION = '安排翻层复测'
MANUAL_ACTION = '待补烘房层签'
NORMAL_ACTION = '正常出窑'
WORKFLOW = '同窑同层视为一个工位，补测要留见证点且不能跨冷却窗口。'
PLACEMENT_MODE = 'context_lock'
POOL_LIMIT = 2
SEPARATE_CONTEXTS = True
HAS_WORKBENCH = True
SAMPLE_NAME = 'kilnboard_register.csv'

FIELDS = (
    Field('thickness', '板材厚度', 'mm', 10, 38, False),
    Field('hours', '烘干时长', '小时', 6, 39, False),
    Field('steam', '蒸汽阀开度', '%', 12, 95, False),
    Field('inlet', '进料含水率', '%', 14, 39, False),
    Field('level', '堆垛层位', '层', 1, 8, True),
    Field('vent', '风阀开度', '%', 11, 91, False),
)
