from dataclasses import dataclass, field


@dataclass
class xlsx_datas_device_item():
    """
    csv数据的格式
    """

    name: str = ""  # device name
    data: list = field(default_factory=list)  # 数据[13,313,]


@dataclass
class xlsx_datas_phase_item():
    """
    csv数据的格式
    """
    name: str = ""  # A相
    data: list = field(default_factory=list)  # 数据[xlsx_datas_device_item]


@dataclass
class xlsx_datas_item_x():
    name: list = field(default_factory=list)  # x轴数据 数据项描述
    data: list = field(default_factory=list)  # x轴数据
    pass


@dataclass
class xlsx_datas_item():
    x: xlsx_datas_item_x = field(default_factory=xlsx_datas_item_x)  # x轴数据 xlsx_datas_item_x
    y: list = field(default_factory=list)  # y轴数据 [xlsx_datas_phase_item]
    pass


@dataclass
class xlsx_datas_type_item():
    name: str = ""  # 功率 电压啥的
    data: xlsx_datas_item = field(default_factory=xlsx_datas_item)  # xlsx_datas_item
    pass


@dataclass
class xlsx_data():
    """
    csv数据的格式
    """
    rated_voltage: float = 0  # 额定电压
    rated_voltage_unit: str = ''
    rated_frequency: float = 0  # 额定频率
    rated_frequency_unit: str = ''
    name: str = ""  # 各种描述

    data: list = field(default_factory=list)  # [xlsx_datas_type_item]

# 获取柱状图三相流数据
def get_three_phase_flow_data_column(self):
    """
       获取单个文件数据
       :param now datetime类型的时间数据
       :param data_origin_port 数据串口
       :return:
    """
    base_number = 1000000  # ppm 化简

    datas = self.xlsx_parser.read_data(files_path=[path_dict])
    logger.error(path)
    data = datas[0]
    data_each_counts = 36
    return_data = xlsx_data()

    # 删除含缺失值的行
    data_clean = data.dropna()
    df_colum_0_unique = data_clean.drop_duplicates(subset=[data_clean.columns[0]])
    df_colum_1_unique = data_clean.drop_duplicates(subset=[data_clean.columns[1]])

    return_data.rated_frequency = float("".join(re.findall(r'[0-9]', df_colum_1_unique.iloc[0, 1])))
    return_data.rated_frequency_unit = "".join(re.findall(r'[A-Za-z]', df_colum_1_unique.iloc[0, 1]))
    return_data.rated_voltage = float(
        "".join(re.findall(r'[0-9]', df_colum_0_unique.iloc[0, 0].split(",")[0])))
    return_data.rated_voltage_unit = "".join(
        re.findall(r'[A-Za-z]', df_colum_0_unique.iloc[0, 0].split(",")[0]))

    # 获得四项数据名  # 收集X轴
    xlsx_datas_type_item_obj_x_data = []
    for row in range(data_clean.shape[0]):

        temp = row / data_each_counts
        index = math.floor(temp)
        if temp == 0:
            xlsx_datas_type_item_obj = xlsx_datas_type_item()
            xlsx_datas_type_item_obj.name = "功率W"
            # 收集x轴
            xlsx_datas_type_item_obj.data.x.name.append(data.iloc[2, 2])
            xlsx_datas_type_item_obj.data.x.name.append("电流/A")
            return_data.data.append(xlsx_datas_type_item_obj)
            pass
        elif temp == 1:
            xlsx_datas_type_item_obj = xlsx_datas_type_item()
            xlsx_datas_type_item_obj.name = "电压"
            # 收集x轴
            xlsx_datas_type_item_obj.data.x.name.append(data.iloc[2, 2])
            xlsx_datas_type_item_obj.data.x.name.append("电流/A")
            return_data.data.append(xlsx_datas_type_item_obj)
            return_data.data[index - 1].data.x.data = xlsx_datas_type_item_obj_x_data
            xlsx_datas_type_item_obj_x_data = []
            pass
        elif temp == 2:
            xlsx_datas_type_item_obj = xlsx_datas_type_item()
            xlsx_datas_type_item_obj.name = "电流"
            # 收集x轴
            xlsx_datas_type_item_obj.data.x.name.append(data.iloc[2, 2])
            xlsx_datas_type_item_obj.data.x.name.append("电流/A")
            return_data.data.append(xlsx_datas_type_item_obj)
            return_data.data[index - 1].data.x.data = xlsx_datas_type_item_obj_x_data
            xlsx_datas_type_item_obj_x_data = []
            pass
        elif temp == 3:
            xlsx_datas_type_item_obj = xlsx_datas_type_item()
            xlsx_datas_type_item_obj.name = "相角"
            # 收集x轴
            xlsx_datas_type_item_obj.data.x.name.append(data.iloc[2, 2])
            xlsx_datas_type_item_obj.data.x.name.append("电流/A")
            return_data.data.append(xlsx_datas_type_item_obj)
            return_data.data[index - 1].data.x.data = xlsx_datas_type_item_obj_x_data
            xlsx_datas_type_item_obj_x_data = []
        # 额定电流单位
        rated_current_unit = "".join(re.findall(r'[A-Za-z]', data_clean.iloc[row, 0].strip().split(",")[1]))
        if rated_current_unit == "mA":
            rated_current = float(
                "".join(re.findall(r'[0-9]', data_clean.iloc[row, 0].strip().split(",")[1]))) / 1000
            pass
        else:
            rated_current = float("".join(re.findall(r'[0-9]', data_clean.iloc[row, 0].strip().split(",")[1])))
            pass
        # 相角 和 额定电流
        xlsx_datas_type_item_obj_x_data.append([data_clean.iloc[row, 2], rated_current])
    return_data.data[- 1].data.x.data = xlsx_datas_type_item_obj_x_data

    # 设置y轴数据
    # A相 B相 C相
    df_rows_2_4_unique = data.iloc[2, 4:].dropna()
    # 设备名列
    df_rows_3_4 = data.iloc[3, 4:]
    for row in range(data_clean.shape[0]):
        temp = row / data_each_counts
        index = math.floor(temp)
        if temp == 0 or temp == 1 or temp == 2 or temp == 3:
            # A相 B相 C相
            for j in range(df_rows_2_4_unique.shape[0]):
                xlsx_datas_phase_item_obj = xlsx_datas_phase_item()
                xlsx_datas_phase_item_obj.name = df_rows_2_4_unique.iloc[j]
                # 两个设备
                device_series = df_rows_3_4.drop_duplicates()[:-2]
                for device_row in range(device_series.shape[0]):
                    xlsx_datas_device_item_obj = xlsx_datas_device_item()
                    xlsx_datas_device_item_obj.name = device_series.iloc[device_row]

                    xlsx_datas_phase_item_obj.data.append(xlsx_datas_device_item_obj)
                    pass
                return_data.data[index].data.y.append(xlsx_datas_phase_item_obj)
            pass
    # 设置y的具体值
    for row in range(data_clean.shape[0]):
        temp = row / data_each_counts
        index = math.floor(temp)
        # A相 B相 C相
        for j in range(df_rows_2_4_unique.shape[0]):

            # 两个设备
            device_series = df_rows_3_4.drop_duplicates()[:-2]
            for device_row in range(device_series.shape[0]):
                return_data.data[index].data.y[j].data[device_row].data.append(
                    data_clean.iloc[row, int(df_rows_2_4_unique.index[j][-1]) + device_row])
                pass

            pass
    return return_data