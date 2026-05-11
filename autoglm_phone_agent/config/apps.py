# SPDX-License-Identifier: Apache-2.0
# App name → package mapping (subset; extend as needed). See also:
# https://github.com/zai-org/Open-AutoGLM/blob/main/phone_agent/config/apps.py

from __future__ import annotations

APP_PACKAGES: dict[str, str] = {
    "微信": "com.tencent.mm",
    "QQ": "com.tencent.mobileqq",
    "微博": "com.sina.weibo",
    "淘宝": "com.taobao.taobao",
    "京东": "com.jingdong.app.mall",
    "拼多多": "com.xunmeng.pinduoduo",
    "小红书": "com.xingin.xhs",
    "豆瓣": "com.douban.frodo",
    "知乎": "com.zhihu.android",
    "高德地图": "com.autonavi.minimap",
    "百度地图": "com.baidu.BaiduMap",
    "美团": "com.sankuai.meituan",
    "大众点评": "com.dianping.v1",
    "饿了么": "me.ele",
    "携程": "ctrip.android.view",
    "铁路12306": "com.MobileTicket",
    "12306": "com.MobileTicket",
    "滴滴出行": "com.sdu.didi.psnger",
    "bilibili": "tv.danmaku.bili",
    "抖音": "com.ss.android.ugc.aweme",
    "腾讯视频": "com.tencent.qqlive",
    "爱奇艺": "com.qiyi.video",
    "网易云音乐": "com.netease.cloudmusic",
    "QQ音乐": "com.tencent.qqmusic",
    "汽水音乐": "com.luna.music",
    "喜马拉雅": "com.ximalaya.ting.android",
    "番茄小说": "com.dragon.read",
    "飞书": "com.ss.android.lark",
    "豆包": "com.larus.nova",
    "腾讯新闻": "com.tencent.news",
    "今日头条": "com.ss.android.article.news",
    "Settings": "com.android.settings",
    "AndroidSystemSettings": "com.android.settings",
}


def get_package_name(app_name: str) -> str | None:
    return APP_PACKAGES.get(app_name)


def get_app_name(package_name: str) -> str | None:
    for name, package in APP_PACKAGES.items():
        if package == package_name:
            return name
    return None


def list_supported_apps() -> list[str]:
    return list(APP_PACKAGES.keys())
