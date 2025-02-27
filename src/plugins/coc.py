import json
from collections import defaultdict

from nonebot import on_command, on_message, on_notice, require, get_driver
from nonebot.log import logger
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot
from nonebot.adapters.cqhttp import Message, MessageSegment, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import startswith
import requests
import demjson
import random
import math
import time as _time

from src.libraries.image import *

driver = get_driver()


@driver.on_startup
def _():
    logger.info("Kiba Kernel -> Load \"COC\" successfully")


class CocEvent:
    def __init__(self, time, role_name, s1, s2, index, operation, value):
        self.time = time
        self.role_name = role_name
        self.s1 = s1
        self.s2 = s2
        self.index = index
        self.operation = operation
        self.value = value


class RollExpError(Exception):
    def __init__(self, msg):
        self.msg = msg


def song_txt(music, file):
    return [
        {
            "type": "image",
            "data": {
                "file": f"{file}"
            }
        },
        {
            "type": "text",
            "data": {
                "text": f"♪ {music['id']} ({music['type']}) >\n"
            }
        },
        {
            "type": "text",
            "data": {
                "text": f"{music['title']}"
            }
        },
        {
            "type": "text",
            "data": {
                "text": f"\n分类 > {music['genre']}\n等级 > {' ▸ '.join(music['level'])}"
            }
        }
    ]


bg_text = """姓名：%s    玩家：%s
职业：%s    年龄：%s    性别：%s
住地：%s    出身：%s
形象描述：%s
思想与信念：%s
重要之人：%s
意义非凡之地：%s
宝贵之物：%s
特质：%s
伤口和疤痕：%s
恐惧症和狂躁症：%s
持有物品：%s"""
showall_text = """姓名：%s    玩家：%s
职业：%s    年龄：%s    性别：%s
住地：%s    出身：%s
技能/属性信息：
%s
形象描述：%s
思想与信念：%s
重要之人：%s
意义非凡之地：%s
宝贵之物：%s
特质：%s
伤口和疤痕：%s
恐惧症和狂躁症：%s
持有物品：%s"""
with open('src/static/career_data.json', encoding='utf-8') as f:
    career_data = json.load(f)
role_cache = {}
time_event = []
binding_map = {}
stats_alias_map = {'力量': 'str', '体质': 'con', '体型': 'siz', '敏捷': 'dex', '外貌': 'app', '教育': 'edu', '智力': 'int',
                   '意志': 'pow', '体格': 'tg', '移动': 'mov', '生命': 'hp', '理智': 'san', '魔法': 'mp', '幸运': 'luck', '灵感': 'int'}


def check_map(role):
    for key in binding_map:
        if binding_map[key] == role:
            return False
    return True


def flush_buffer(time):
    s = ""
    deletion = []
    for i in range(len(time_event)):
        event = time_event[i]
        event.time -= time
        if event.time <= 0:
            if event.index == -1:
                if event.operation == 0:
                    role_cache[event.role_name][event.s1][event.s2] = event.value
                    s += "▾ COC - 能力变化\n【%s】的能力【%s】变成了【%d】！\n" % (event.role_name, event.s2, event.value)
                elif event.operation == 1:
                    role_cache[event.role_name][event.s1][event.s2] += event.value
                    s += "▾ COC - 能力变化\n【%s】的能力【%s】上升了【%d】！\n" % (event.role_name, event.s2, event.value)
                elif event.operation == 2:
                    role_cache[event.role_name][event.s1][event.s2] -= event.value
                    s += "▾ COC - 能力变化\n【%s】的能力【%s】下降了【%d】！\n" % (event.role_name, event.s2, event.value)
            else:
                skill = role_cache[event.role_name][event.s1][event.index]
                if event.operation == 0:
                    role_cache[event.role_name][event.s1][event.index][event.s2] = event.value
                    s += "▾ COC - 技能变化\n【%s】的技能【%s】变成了【%d】！\n" % (event.role_name, skill['label'], event.value)
                elif event.operation == 1:
                    role_cache[event.role_name][event.s1][event.index][event.s2] += event.value
                    s += "▾ COC - 技能变化\n【%s】的技能【%s】上升了【%d】！\n" % (event.role_name, skill['label'], event.value)
                elif event.operation == 2:
                    role_cache[event.role_name][event.s1][event.index][event.s2] -= event.value
                    s += "▾ COC - 技能变化\n【%s】的技能【%s】下降了【%d】！\n" % (event.role_name, skill['label'], event.value)
            deletion.append(i)
    for i in deletion:
        del time_event[i]
    return s.strip()


def stat_modify(role, key: str, op: int, value: int, time=0):
    key = key.lower()
    try:
        key = stats_alias_map[key]
    except KeyError:
        pass
    try:
        r = role['stats'][key]
        event = CocEvent(time, role['name'], 'stats', key, -1, op, value)
        time_event.append(event)
        return flush_buffer(0), True
    except KeyError:
        pass
    if len(key) <= 1:
        return "", False
    for skill in role['skills']:
        if key in skill['label']:
            index = role['skills'].index(skill)
            exp = "role_cache['%s']['skills'][%d]['sum']" % (role['name'], index)
            event = CocEvent(time, role['name'], 'skills', 'sum', index, op, value)
            time_event.append(event)
            return flush_buffer(0), True
    return "", False


def search_check(role, key: str):
    key = key.lower()
    try:
        key = stats_alias_map[key]
    except KeyError:
        pass
    try:
        return role['stats'][key], True
    except KeyError:
        pass
    if len(key) <= 1:
        return "", False
    for skill in role['skills']:
        if key in skill['label']:
            return skill['sum'], True
    return "", False


def roll_term(rterm: str):
    arr = rterm.split('d')
    if len(arr) == 1:
        return "%d" % int(arr[0]), int(arr[0])
    elif len(arr) == 2:
        exp = ""
        total = 0
        for i in range(int(arr[0])):
            v = random.randint(1, int(arr[1]))
            exp += str(v) + "+"
            total += v
        return exp[:-1], total
    raise RollExpError


def roll_expression(rexp: str):
    rexp = rexp.lower()
    arr = rexp.split("+")
    exp = ""
    total = 0
    for elem in arr:
        s, i = roll_term(elem)
        exp += s + "+"
        total += i
    return "%s=%s=%d" % (rexp, exp[:-1], total), total


def gen_bg_text(role):
    career = career_data[role['career'] - 1]['label']
    gender = "女"
    items = ' '.join(role['item'])
    if role['gender'] == 1:
        gender = "男"
    t = (role['name'], role['player_name'], career, role['age'], gender, role['address'], role['from'],
         role['bg'][0], role['bg'][1], role['bg'][2], role['bg'][3], role['bg'][4], role['bg'][5], role['bg'][6],
         role['bg'][7], items)
    return bg_text % t


def gen_showall_text(role):
    career = career_data[role['career'] - 1]['label']
    gender = "女"
    items = ' '.join(role['item'])
    ability_str = ""
    for st in ['str', 'con', 'siz', 'dex', 'app', 'edu', 'int', 'pow', 'luck', 'hp', 'mp', 'mov', 'tg', 'san']:
        for st2 in stats_alias_map:
            if st == stats_alias_map[st2]:
                ability_str += "%s: %d\n" % (st2, role['stats'][st])
    ability_str += "\n"
    for sk in role['skills']:
        if sk['sum'] is None:
            sk['sum'] = 0
        ability_str += "%s: %d/%d/%d\n" % (sk['label'], sk['sum'], int(sk['sum'] / 2), int(sk['sum'] / 5))
    if role['gender'] == 1:
        gender = "男"
    t = (role['name'], role['player_name'], career, role['age'], gender, role['address'], role['from'], ability_str,
         role['bg'][0], role['bg'][1], role['bg'][2], role['bg'][3], role['bg'][4], role['bg'][5], role['bg'][6],
         role['bg'][7], items)
    return showall_text % t


def check(nickname, stat_name, value):
    rand = random.randint(1, 100)
    text = ""
    if rand <= value:
        if rand <= 3:
            text = "大成功"
        elif rand <= math.floor(value / 5):
            text = "极难成功"
        elif rand <= math.floor(value / 2):
            text = "困难成功"
        else:
            text = "成功"
    else:
        if rand > value:
            if rand >= 98:
                text = "大失败"
            else:
                text = "失败"
    return "▾ COC - 检定结果\n【%s】进行【%s】检定: D100=%d/%d %s" % (nickname, stat_name, rand, value, text)

coc_help = on_command('coc.help')

@coc_help.handle()
async def _(bot: Bot, event: Event, state: T_State):
    help_str = '''▼ 跑团模块可用命令 | Commands For COC
---------------------------------------------------------
coc.help 输出此消息
coc.bind <角色名称> 绑定角色
coc.r/roll <掷骰表达式> 掷骰
coc.rc/rollcheck <技能/属性> [值] 技能/属性检定
coc.sc/sancheck <成功> <失败> 理智检定
coc.stat/st <技能/属性> <add|sub|set> <值> [触发时间（小时）] 增加/减少/设置属性值，可设定触发时间
coc.time <pass> [小时] 设置经过时间
coc.query/q <玩家名/QQ> <技能/属性> 查询某玩家的某属性
coc.intro/.i <玩家名> 查询此角色的基本信息
coc.showall/.sa 获取当前玩家的所有信息（将私聊发送）
coc.unbind 解绑角色
---------------------------------------------------------'''
    await coc_help.send(Message([{
        "type": "image",
        "data": {
            "file": f"base64://{str(image_to_base64(text_to_image(help_str)), encoding='utf-8')}"
        }
    }]))
    await coc_help.finish("车卡网址：https://www.diving-fish.com/coc_card")

unbind = on_command("coc.unbind")


@unbind.handle()
async def _(bot: Bot, event: Event, state: dict):
    qq = int(event.get_user_id())
    try:
        var = binding_map[qq]
        del role_cache[binding_map[qq]]
        del binding_map[qq]
        await unbind.send("▾ COC - 解绑\n已经解绑成功啦！")
    except KeyError:
        await unbind.send("▿ COC - 解绑 - 无角色\n你还未绑定角色哦~")


intro = on_command('coc.intro ', aliases={'coc.i '})


@intro.handle()
async def _(bot: Bot, event: Event, state: dict):
    name = str(event.get_message()).strip()
    try:
        await intro.send(gen_bg_text(role_cache[name]))
    except KeyError:
        await intro.send("▿ COC - 找不到角色\n未找到【%s】！这个角色似乎并没有出现在这个剧本里呢~" % name)


time = on_command('coc.time ')


@time.handle()
async def _(bot: Bot, event: Event, state: dict):
    t = int(str(event.get_message()).strip().split(' ')[-1])
    s = flush_buffer(t)
    if s == "":
        await time.send("▿ COC - 角色变化\n经过了%d小时，但没有玩家的能力值发生变化。" % t)
    else:
        await time.send("▾ COC - 角色变化\n经过%d小时后，玩家的能力发生了如下变化：\n%s" % (t, s))


stat = on_command('coc.stat ', aliases={'coc.st '})


@stat.handle()
async def _(bot: Bot, event: Event, state: dict):
    argv = str(event.get_message()).strip().split(' ')
    argc = len(argv)
    if len(argv) != 1 and len(argv) != 3 and len(argv) != 4:
        await stat.send("▿ COC - 格式错误\n你这白痴又弄错命令格式了！给我记好了，正确的格式是.stat <技能/属性> <add|sub|set> <值> [触发时间（小时）]！")
        return
    role = None
    try:
        role = role_cache[binding_map[int(event.get_user_id())]]
    except KeyError:
        await stat.send("▿ COC - 角色未绑定\n【%s】看起来还没绑定角色呢。输入.bind <角色名称> 进行绑定吧？" % (event.sender.nickname))
        return
    if argc == 1:
        stat_name = argv[0]
        value, err = search_check(role, stat_name)
        if not err:
            await stat.send("▿ COC - 无能力值\n未找到能力值【%s】！真的有这个能力吗？" % stat_name)
            return
        await stat.send("▾ COC - 能力值\n【%s】的能力值【%s】为：%d/%d/%d" % (role['name'], stat_name, value, int(value / 2), int(value / 5)))
        return
    elif argc >= 3:
        time = 0
        if argc == 4:
            time = int(argv[3])
        m = {'add': 1, 'sub': 2, 'set': 0}
        try:
            op = m[argv[1]]
        except KeyError:
            await stat.send("▿ COC - 不支持\n看起来命令不支持【%s】这个操作呢~" % argv[1])
            return
        s, e = stat_modify(role, argv[0], op, int(argv[2]), time)
        if not e:
            await stat.send("▿ COC - 无能力值\n未找到能力值【%s】！真的有这个能力吗？" % argv[0])
        else:
            if time == 0:
                await stat.send(s)
            else:
                await stat.send("▾ COC - 变化冷却\n【%s】的【%s】会在%d小时后发生变化~" % (role['name'], argv[0], time))


showall = on_command('coc.showall', aliases={'coc.sa'})


@showall.handle()
async def _(bot: Bot, event: Event, state: dict):
    qq = int(event.get_user_id())
    try:
        nickname = binding_map[qq]
        role = role_cache[nickname]
        await showall.send(gen_showall_text(role), ensure_private=True)
        await showall.send("▾ COC - 角色信息\n已发送私聊消息~", at_sender=True)
    except KeyError:
        await showall.send("▿ COC - 角色未绑定\n【%s】看起来还没绑定角色呢。输入.bind <角色名称> 进行绑定吧？" % event.sender.nickname)
        return


query = on_command('coc.query ', aliases={'coc.q '})


@query.handle()
async def _(bot: Bot, event: Event, state: dict):
    argv = str(event.get_message()).strip().split(' ')
    if len(argv) != 2:
        await query.send("▿ COC - 格式错误\n你这白痴又弄错命令格式了！给我记好了，正确的格式是.q <玩家名/QQ> <技能/属性>！")
        return
    role = None
    try:
        role = role_cache[binding_map[argv[0]]]
    except Exception:
        try:
            role = role_cache[argv[0]]
        except Exception:
            await query.send("▿ COC - 找不到角色\n未找到【%s】！这个角色似乎并没有出现在这个剧本里呢~" % argv[0])
            return
    stat_name = argv[1]
    value, err = search_check(role, stat_name)
    if not err:
        await query.send("▿ COC - 无能力值\n未找到能力值【%s】！真的有这个能力吗？" % stat_name)
        return
    await query.send("▾ COC - 能力值\n【%s】的能力值【%s】为：%d/%d/%d" % (role['name'], stat_name, value, int(value / 2), int(value / 5)))


roll = on_command('coc.roll ', aliases={'coc.r '})


@roll.handle()
async def _(bot: Bot, event: Event, state: dict):
    result = roll_expression(str(event.get_message()).strip())
    name = event.sender.nickname
    try:
        name = binding_map[int(event.get_user_id())]
    except KeyError:
        pass
    await roll.send("▿ COC - 掷骰子\n【%s】的掷骰结果：%s" % (name, result[0]))
    
    
sancheck = on_command('coc.sancheck ', aliases={'coc.sc '})


@sancheck.handle()
async def _(bot: Bot, event: Event, state: dict):
    qq = int(event.get_user_id())
    argv = str(event.get_message()).strip().split(' ')
    try:
        nickname = binding_map[qq]
        if len(argv) != 2:
            await sancheck.send("▿ COC - 格式错误\n你这白痴又弄错命令格式了！给我记好了，正确的格式是.sc <成功> <失败>！")
            return
        role = role_cache[nickname]
        value = random.randint(1, 100)
        sanity = role['stats']['san']
        if value > sanity:
            s, v = roll_expression(argv[1])
            role['stats']['san'] -= v
            await sancheck.send("▿ COC - 理智检定失败\n【%s】的理智检定：%d/%d 失败，理智扣除%s点，剩余%d点" % (nickname, value, sanity, s, role['stats']['san']))
        else:
            s, v = roll_expression(argv[0])
            role['stats']['san'] -= v
            await sancheck.send("▾ COC - 理智检定成功\n【%s】的理智检定：%d/%d 成功，理智扣除%s点，剩余%d点" % (nickname, value, sanity, s, role['stats']['san']))
    except KeyError:
        await sancheck.send("▿ COC - 角色未绑定\n【%s】看起来还没绑定角色呢。输入.bind <角色名称> 进行绑定吧？" % (event.sender.nickname))
        return
    
    
rollcheck = on_command('coc.rollcheck ', aliases={'coc.rc '})


@rollcheck.handle()
async def _(bot: Bot, event: Event, state: dict):
    qq = int(event.get_user_id())
    try:
        nickname = binding_map[qq]
    except KeyError:
        await rollcheck.send("▿ COC - 角色未绑定\n【%s】看起来还没绑定角色呢。输入.bind <角色名称> 进行绑定吧？" % (event.sender.nickname))
        return
    argv = str(event.get_message()).strip().split(' ')
    try:
        stat_name = argv[0]
        if len(argv) == 2:
            value = int(argv[1])
            await rollcheck.send(check(nickname, stat_name, value))
            return
        try:
            role = role_cache[nickname]
            value, err = search_check(role, stat_name)
            if not err:
                await rollcheck.send("▿ COC - 无能力值\n未找到能力值【%s】！真的有这个能力吗？" % stat_name)
                return
            await rollcheck.send(check(nickname, stat_name, value))
        except KeyError:
            await rollcheck.send("▿ COC - 角色未绑定\n【%s】看起来还没绑定角色呢。输入.bind <角色名称> 进行绑定吧？" % (event.sender.nickname))
            return
    except Exception:
        await rollcheck.send("▿ COC - 格式错误\n你这白痴又弄错命令格式了！给我记好了，正确的格式是.rc <技能/属性> [值]！")
        return


bind = on_command('coc.bind ')


@bind.handle()
async def _(bot: Bot, event: Event, state: dict):
    name = str(event.get_message()).strip()
    qq = int(event.get_user_id())
    try:
        var = binding_map[qq]
    except KeyError:
        try:
            var = role_cache[name]
        except KeyError:
            text = requests.get("http://47.100.50.175:25565/query", {"name": name}).text
            if text == "{}":
                await bind.send("▿ COC - 找不到角色\n小犽没能找到角色【%s】，下次再出错就把你拉入黑名单了哦！" % name)
                return
            role_cache[name] = demjson.decode(text, encoding='utf-8')
        if check_map(name):
            binding_map[qq] = name
        else:
            await bind.send("▿ COC - 角色已被绑定\n这个角色已经绑定过啦！难道还想两个人控制一个角色吗？！")
            return
        await bind.send("▾ COC - 绑定成功\n绑定成功！现在千雪已经认为【%s】就是【%s】了哦！" % (event.sender.nickname, name))
        return
    await bind.send("▿ COC - 已绑定\n你已经绑定过角色了哟~")