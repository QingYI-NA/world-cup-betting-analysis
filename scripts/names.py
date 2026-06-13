"""
中英文队名/场馆映射
"""

TEAM_CN = {
    "Mexico": "墨西哥", "South Africa": "南非", "South Korea": "韩国",
    "Canada": "加拿大", "Switzerland": "瑞士", "Qatar": "卡塔尔",
    "Brazil": "巴西", "Morocco": "摩洛哥", "Haiti": "海地",
    "Scotland": "苏格兰", "United States": "美国", "Paraguay": "巴拉圭",
    "Australia": "澳大利亚", "Germany": "德国", "Ecuador": "厄瓜多尔",
    "Ivory Coast": "科特迪瓦", "Curacao": "库拉索",
    "Netherlands": "荷兰", "Japan": "日本", "Tunisia": "突尼斯",
    "Belgium": "比利时", "Iran": "伊朗", "Egypt": "埃及",
    "New Zealand": "新西兰", "Spain": "西班牙", "Uruguay": "乌拉圭",
    "Saudi Arabia": "沙特阿拉伯", "Cape Verde": "佛得角",
    "France": "法国", "Senegal": "塞内加尔", "Norway": "挪威",
    "Argentina": "阿根廷", "Austria": "奥地利", "Algeria": "阿尔及利亚",
    "Jordan": "约旦", "Portugal": "葡萄牙", "Colombia": "哥伦比亚",
    "Uzbekistan": "乌兹别克斯坦", "England": "英格兰",
    "Croatia": "克罗地亚", "Ghana": "加纳", "Panama": "巴拿马",
    "Czechia": "捷克", "Czech Republic": "捷克",
    "Bosnia-Herzegovina": "波黑", "Bosnia & Herzegovina": "波黑",
    "South Korea": "韩国", "Korea Republic": "韩国",
    "DR Congo": "民主刚果", "Côte d'Ivoire": "科特迪瓦",
    "Curaçao": "库拉索", "Cabo Verde": "佛得角",
}

VENUE_CN = {
    "metlife": "大都会人寿球场(纽约)", "sofi": "SoFi球场(洛杉矶)",
    "att": "AT&T球场(达拉斯)", "hard_rock": "硬石球场(迈阿密)",
    "mercedes_benz": "梅赛德斯-奔驰球场(亚特兰大)",
    "gillette": "吉列球场(波士顿)", "nrg": "NRG球场(休斯顿)",
    "arrowhead": "箭头球场(堪萨斯城)", "lincoln": "林肯金融球场(费城)",
    "levis": "李维斯球场(旧金山)", "lumen": "流明球场(西雅图)",
    "azteca": "阿兹特克球场(墨西哥城)", "akron": "阿克伦球场(瓜达拉哈拉)",
    "bbva": "BBVA球场(蒙特雷)", "bmo": "BMO球场(多伦多)",
    "bc_place": "BC广场(温哥华)",
}

VENUE_CITY_CN = {
    "East Rutherford": "纽约", "Inglewood": "洛杉矶", "Arlington": "达拉斯",
    "Miami Gardens": "迈阿密", "Atlanta": "亚特兰大", "Foxborough": "波士顿",
    "Houston": "休斯顿", "Kansas City": "堪萨斯城", "Philadelphia": "费城",
    "Santa Clara": "旧金山", "Seattle": "西雅图",
    "Mexico City": "墨西哥城", "Guadalajara": "瓜达拉哈拉",
    "Guadalupe": "蒙特雷", "Toronto": "多伦多", "Vancouver": "温哥华",
}


def cn(name):
    """队名转中文"""
    return TEAM_CN.get(name, name)


def venue_cn(venue_id):
    """场馆ID转中文名"""
    return VENUE_CN.get(venue_id, venue_id)


def home_away_label(team, is_home):
    """主客标签"""
    return f"{'🏠' if is_home else '✈️'} {cn(team)}"
