# SPDX-License-Identifier: Apache-2.0
# HarmonyOS bundle / ability mappings — adapted from Open-AutoGLM phone_agent/config/apps_harmonyos.py

from __future__ import annotations

APP_ABILITIES: dict[str, str] = {
    "com.taobao.taobao4hmos": "Taobao_mainAbility",
    "com.jd.hm.mall": "EntryAbility",
    "com.ss.hm.ugc.aweme": "MainAbility",
    "com.zhihu.hmos": "PhoneAbility",
    "com.sankuai.hmeituan": "MainAbility",
    "com.sankuai.dianping": "MainAbility",
    "com.huawei.hmos.settings": "com.huawei.hmos.settings.MainAbility",
    "com.huawei.hmos.browser": "MainAbility",
    "com.ohos.contacts": "com.ohos.contacts.MainAbility",
}

APP_PACKAGES: dict[str, str] = {
    "微信": "com.tencent.wechat",
    "QQ": "com.tencent.mqq",
    "微博": "com.sina.weibo.stage",
    "淘宝": "com.taobao.taobao4hmos",
    "京东": "com.jd.hm.mall",
    "拼多多": "com.xunmeng.pinduoduo.hos",
    "小红书": "com.xingin.xhs_hos",
    "知乎": "com.zhihu.hmos",
    "高德地图": "com.amap.hmapp",
    "百度地图": "com.baidu.hmmap",
    "美团": "com.sankuai.hmeituan",
    "美团外卖": "com.meituan.takeaway",
    "大众点评": "com.sankuai.dianping",
    "铁路12306": "com.chinarailway.ticketingHM",
    "12306": "com.chinarailway.ticketingHM",
    "滴滴出行": "com.sdu.didi.hmos.psnger",
    "bilibili": "yylx.danmaku.bili",
    "抖音": "com.ss.hm.ugc.aweme",
    "快手": "com.kuaishou.hmapp",
    "腾讯视频": "com.tencent.videohm",
    "爱奇艺": "com.qiyi.video.hmy",
    "QQ音乐": "com.tencent.hm.qqmusic",
    "汽水音乐": "com.luna.hm.music",
    "喜马拉雅": "com.ximalaya.ting.xmharmony",
    "今日头条": "com.ss.hm.article.news",
    "飞书": "com.ss.feishu",
    "豆包": "com.larus.nova.hm",
    "支付宝": "com.alipay.mobile.client",
    "设置": "com.huawei.hmos.settings",
    "Settings": "com.huawei.hmos.settings",
    "AndroidSystemSettings": "com.huawei.hmos.settings",
    "浏览器": "com.huawei.hmos.browser",
    "联系人": "com.ohos.contacts",
    "电话": "com.ohos.callui",
}
