from enum import Enum

class AppState(Enum):
    #程序当前状态
    # 初始化状态
    INITIALIZED = {'text':"INITIALIZED","value":0}
    #应用实验状态
    CONNECTED =  {'text':"CONNECTED","value":1}
    # #设备配置状态
    # CONFIGURING ={'text':"CONFIGURING","value":2}
    # #开始监测数据状态
    # MONITORING = {'text':"MONITORING","value":3}

    def __lt__(self, other):
        if other is None:
            return False
        return self.value.get("value") < other.value.get("value")

    def __le__(self, other):
        if other is None:
            return False
        return self.value.get("value") <= other.value.get("value")

    def __gt__(self, other):
        if other is None:
            return False
        return self.value.get("value") > other.value.get("value")

    def __ge__(self, other):
        if other is None:
            return False
        return self.value.get("value") >= other.value.get("value")
    def __eq__(self, other):
        if other is None:
            return False
        return self.value.get("value") == other.value.get("value")
    def __ne__(self, other):
        if other is None:
            return False
        return self.value.get("value") != other.value.get("value")
class AnimalGender(Enum):
    # 雌性
    FEMALE = True
    # 雄性
    MALE = False

class Tutorial_Type(Enum):
    OVERLAY_GUIDE = 0
    BUBBLE_GUIDE = 1
    ARROW_GUIDE = 2

    def __lt__(self, other):
        if other is None:
            return False
        return self.value < other.value

    def __le__(self, other):
        if other is None:
            return False
        return self.value <= other.value

    def __gt__(self, other):
        if other is None:
            return False
        return self.value > other.value

    def __ge__(self, other):
        if other is None:
            return False
        return self.value >= other.value

    def __eq__(self, other):
        if other is None:
            return False
        return self.value == other.value

    def __ne__(self, other):
        if other is None:
            return False
        return self.value != other.value
class BaseInterfaceType(Enum):
    WINDOW=0
    FRAME=1
    WIDGET = 1

    def __lt__(self, other):
        if other is None:
            return False
        return self.value < other.value

    def __le__(self, other):
        if other is None:
            return False
        return self.value <= other.value

    def __gt__(self, other):
        if other is None:
            return False
        return self.value > other.value

    def __ge__(self, other):
        if other is None:
            return False
        return self.value >= other.value

    def __eq__(self, other):
        if other is None:
            return False
        return self.value == other.value

    def __ne__(self, other):
        if other is None:
            return False
        return self.value != other.value
class Frame_state(Enum):
    Default = 0
    Opening = 1
    Closed = 2

    def __lt__(self, other):
        if other is None:
            return False
        return self.value < other.value

    def __le__(self, other):
        if other is None:
            return False
        return self.value <= other.value

    def __gt__(self, other):
        if other is None:
            return False
        return self.value > other.value

    def __ge__(self, other):
        if other is None:
            return False
        return self.value >= other.value

    def __eq__(self, other):
        if other is None:
            return False
        return self.value == other.value

    def __ne__(self, other):
        if other is None:
            return False
        return self.value != other.value