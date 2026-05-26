"""Python 侧：从扁平 features 重建 GIIC 层级功能树（与 midscene feature_tree_build 对齐）。"""

from __future__ import annotations

from typing import Any

SEARCH_FEATURE_LABEL = "搜索框"
SEARCH_REGIONS = frozenset({"search_bar", "search", "search_box", "search_input"})


def _is_search_feature(feat: dict[str, Any]) -> bool:
    region = str(feat.get("region") or "other").lower()
    if region in SEARCH_REGIONS:
        return True
    name = str(feat.get("name") or "").strip()
    return name == SEARCH_FEATURE_LABEL or "搜索框" in name or name in ("搜索", "搜一搜")


REGION_TO_FUNCTION_TYPE = {
    "top_tab": "顶部Tab",
    "bottom_tab": "底部Tab",
    "category_tab": "顶部分类Tab",
    "top": "顶部导航",
    "bottom": "底部导航",
    "side": "侧栏",
    "icon_grid": "图标宫格",
    "button": "按钮",
    "tab": "Tab",
    "list_item": "列表项",
    "search_bar": "搜索框",
    "search": "搜索框",
    "search_box": "搜索框",
    "other": "其他控件",
}


def _apply_icon_grid_heuristic(features: list[dict[str, Any]]) -> None:
    """同屏批量将首页金刚位 other/button/list_item 提升为 icon_grid。"""
    protected = frozenset(
        {
            "bottom_tab",
            "bottom",
            "top_tab",
            "top",
            "category_tab",
            "search_bar",
            "search",
            "search_box",
            "icon_grid",
            "side",
        }
    )
    candidates_regions = frozenset({"button", "other", "list_item", "tab"})

    groups: dict[str, list[dict[str, Any]]] = {}
    for feat in features:
        key = "@@".join(
            [
                str(feat.get("screen_id") or ""),
                str(feat.get("screen_title") or ""),
                str(feat.get("depth") or len(feat.get("path") or [])),
            ]
        )
        groups.setdefault(key, []).append(feat)

    for group in groups.values():
        candidates = []
        for feat in group:
            region = str(feat.get("region") or "other").lower()
            if region in protected:
                continue
            if region in candidates_regions:
                candidates.append(feat)
        has_more = any(
            str(f.get("name") or "").strip() in ("更多服务", "更多", "全部服务")
            for f in group
        )
        if len(candidates) < 5 and not (len(candidates) >= 3 and has_more):
            continue
        for feat in candidates:
            feat["region"] = "icon_grid"


def _infer_active_bottom_tab(group: list[dict[str, Any]]) -> str | None:
    tabs = [
        str(f.get("name") or "").strip()
        for f in group
        if str(f.get("region") or "").lower() in ("bottom_tab", "bottom")
    ]
    tabs = [t for t in tabs if t]
    if not tabs:
        return None
    title = str(group[0].get("screen_title") or "")
    for t in tabs:
        if t and t in title:
            return t
    names = {str(f.get("name") or "").strip() for f in group}
    xiaotuan_signals = {"深度思考", "一键领券", "找优惠", "问小团", "AI小团"}
    if names & xiaotuan_signals:
        for t in tabs:
            if "小团" in t or "AI" in t.upper():
                return t
    iconish = sum(
        1
        for f in group
        if str(f.get("region") or "other").lower()
        in ("icon_grid", "button", "other", "list_item")
    )
    if iconish >= 5:
        for t in tabs:
            if "推荐" in t or "首页" in t:
                return t
        return tabs[0]
    return None


def _reparent_root_tab_content(features: list[dict[str, Any]]) -> None:
    """主界面 Tab 内控件误挂第一层时，归到当前底部 Tab 下（如 小团 > 深度思考）。"""
    path_keys = {" > ".join(str(p) for p in (f.get("path") or [])) for f in features}
    groups: dict[str, list[dict[str, Any]]] = {}
    for feat in features:
        key = str(feat.get("screen_id") or feat.get("screen_title") or "__default__")
        groups.setdefault(key, []).append(feat)

    for group in groups.values():
        active = _infer_active_bottom_tab(group)
        if not active:
            continue
        bottom_tabs = {
            (f.get("path") or [None])[0] if f.get("path") else f.get("name")
            for f in group
            if str(f.get("region") or "").lower() in ("bottom_tab", "bottom")
        }
        for feat in list(group):
            path = feat.get("path") or []
            if not isinstance(path, list) or len(path) != 1:
                continue
            leaf = str(path[0] or "").strip()
            region = str(feat.get("region") or "other").lower()
            if leaf in bottom_tabs or region in ("bottom_tab", "bottom", "top_tab", "top", "search_bar", "icon_grid"):
                continue
            new_path = [active, leaf]
            new_key = " > ".join(new_path)
            if new_key in path_keys:
                features.remove(feat)
                continue
            path_keys.add(new_key)
            feat["path"] = new_path
            feat["depth"] = len(new_path)


def _function_type(region: str | None) -> str:
    return REGION_TO_FUNCTION_TYPE.get((region or "other").lower(), "其他控件")


def _region_for_function_type(function_type: str) -> str | None:
    """将用户填写的功能类型反查 region，便于与 region 映射一致。"""
    ft = (function_type or "").strip()
    if not ft:
        return None
    for region, label in REGION_TO_FUNCTION_TYPE.items():
        if label == ft:
            return region
    return None


def _enrich_feature(raw: dict[str, Any]) -> dict[str, Any]:
    """补齐 path/描述等；保留用户在 Web 端编辑的 function_type、description、location。"""
    feat = dict(raw)
    path = feat.get("path") or []
    if not isinstance(path, list):
        path = [str(path)]
    path = [str(p) for p in path]
    feat["path"] = path
    screen = str(feat.get("screen_title") or "")
    region = str(feat.get("region") or "other")
    user_ft = str(feat.get("function_type") or "").strip()
    if user_ft:
        feat["function_type"] = user_ft
        mapped = _region_for_function_type(user_ft)
        if mapped and region == "other":
            feat["region"] = mapped
    else:
        feat["function_type"] = _function_type(region)
    ft = feat["function_type"]
    desc = str(feat.get("description") or "").strip()
    if not desc:
        feat["description"] = (
            f"所在界面：{screen or '—'}；控件类型：{ft}；"
            f"{'已深度访问' if feat.get('status') == 'visited' else '本页已识别'}"
        )
    if _is_search_feature(feat):
        feat["name"] = SEARCH_FEATURE_LABEL
        feat["region"] = "search_bar"
        if path:
            path[-1] = SEARCH_FEATURE_LABEL
            feat["path"] = path
        else:
            feat["path"] = [SEARCH_FEATURE_LABEL]
        feat["location"] = SEARCH_FEATURE_LABEL
    else:
        loc = str(feat.get("location") or "").strip()
        if not loc:
            feat["location"] = (
                f"{' > '.join(path)} @ {screen}" if screen else " > ".join(path)
            )
    return feat


def build_function_tree_by_path(app_name: str, features: list[dict[str, Any]]) -> dict[str, Any]:
    root: dict[str, Any] = {
        "id": "app-root",
        "name": app_name or "应用",
        "node_type": "application",
        "depth": 0,
        "path": [],
        "children": [],
    }

    enriched = _prepare_features(features)
    enriched.sort(key=lambda f: (len(f.get("path") or []), " > ".join(f.get("path") or [])))

    path_keys: set[str] = set()

    def _find_fn_child(parent: dict[str, Any], seg: str) -> dict[str, Any] | None:
        return next(
            (
                c
                for c in parent.get("children") or []
                if c.get("name") == seg
                and c.get("node_type") in ("function", "module", "screen")
            ),
            None,
        )

    def _upsert_fn(parent: dict[str, Any], segs: list[str], feat: dict[str, Any] | None) -> dict[str, Any]:
        leaf_name = segs[-1]
        parent_prefix = segs[:-1]
        existing = _find_fn_child(parent, leaf_name)
        node: dict[str, Any] = {
            "id": str((feat or {}).get("id") or (existing or {}).get("id") or f"fn-{'-'.join(segs)}"),
            "name": leaf_name,
            "node_type": "function",
            "depth": len(segs),
            "path": parent_prefix,
            "function_type": (feat or {}).get("function_type")
            or (existing or {}).get("function_type")
            or "功能",
            "description": (feat or {}).get("description") or (existing or {}).get("description") or "",
            "location": (feat or {}).get("location") or " > ".join(segs),
            "screen_title": (feat or {}).get("screen_title") or (existing or {}).get("screen_title"),
            "region": (feat or {}).get("region") or (existing or {}).get("region"),
            "status": (feat or {}).get("status") or (existing or {}).get("status") or "listed",
            "feature_id": (feat or {}).get("id") or (existing or {}).get("feature_id"),
            "children": list((existing or {}).get("children") or []),
        }
        if existing:
            existing.update(node)
            return existing
        parent.setdefault("children", []).append(node)
        return node

    for feat in enriched:
        path = [str(p) for p in (feat.get("path") or []) if str(p).strip()]
        if not path:
            continue
        parent = root
        acc: list[str] = []
        for i, segment in enumerate(path):
            acc.append(segment)
            key = " > ".join(acc)
            if key in path_keys:
                ch = _find_fn_child(parent, segment)
                if ch:
                    parent = ch
                continue
            is_leaf = i == len(path) - 1
            ch = _upsert_fn(parent, acc, feat if is_leaf else None)
            path_keys.add(key)
            parent = ch
    return root


def _finalize_app_name(tree: dict[str, Any]) -> dict[str, Any]:
    """统一 app_name 与 function_tree 应用根名称。"""
    app_name = str(tree.get("app_name") or "").strip()
    ft = tree.get("function_tree") or tree.get("function_tree_by_path")
    if isinstance(ft, dict) and ft.get("node_type") == "application":
        root_name = str(ft.get("name") or "").strip()
        if root_name:
            app_name = root_name
    if not app_name:
        app_name = "应用"
    tree["app_name"] = app_name
    if isinstance(ft, dict) and ft.get("node_type") == "application":
        ft["name"] = app_name
    return tree


def _prepare_features(features: list[Any]) -> list[dict[str, Any]]:
    feats = [dict(f) for f in features if isinstance(f, dict)]
    _reparent_root_tab_content(feats)
    _apply_icon_grid_heuristic(feats)
    return [_enrich_feature(f) for f in feats]


def sync_giic_tree_from_features(tree: dict[str, Any]) -> dict[str, Any]:
    """保存/确认时：始终以 features 为准重建 function_tree，避免与表格编辑不一致。"""
    app_name = str(tree.get("app_name") or "应用")
    features = tree.get("features") or []
    if not isinstance(features, list):
        features = []
    tree["features"] = _prepare_features(features)
    tree["function_tree_by_path"] = build_function_tree_by_path(app_name, tree["features"])
    screens = tree.get("screens") or []
    if isinstance(screens, list) and screens:
        tree = ensure_giic_tree({**tree, "function_tree": None})
    else:
        tree["function_tree"] = tree["function_tree_by_path"]
    tree.setdefault("screens", [])
    return _finalize_app_name(tree)


def ensure_giic_tree(tree: dict[str, Any]) -> dict[str, Any]:
    """若子进程未带 function_tree，则由 features/screens 在 Python 侧补齐。"""
    if isinstance(tree.get("function_tree"), dict) and tree["function_tree"].get("children") is not None:
        return tree
    app_name = str(tree.get("app_name") or "应用")
    features = tree.get("features") or []
    if not isinstance(features, list):
        features = []
    tree["features"] = _prepare_features(features)
    tree["function_tree_by_path"] = build_function_tree_by_path(app_name, tree["features"])
    screens = tree.get("screens") or []
    if isinstance(screens, list) and screens:
        root: dict[str, Any] = {
            "id": "app-root",
            "name": app_name,
            "node_type": "application",
            "depth": 0,
            "path": [],
            "children": [],
        }
        feat_by_id = {str(f.get("id")): f for f in tree["features"]}
        for scr in screens:
            if not isinstance(scr, dict):
                continue
            path = scr.get("path") or []
            path_label = " > ".join(str(p) for p in path) if path else "主界面"
            screen_node: dict[str, Any] = {
                "id": str(scr.get("id") or f"screen-{scr.get('visit_order')}"),
                "name": f"{scr.get('screen_title') or '界面'}（{path_label}）",
                "node_type": "screen",
                "depth": int(scr.get("depth") or 0) + 1,
                "path": list(path) if isinstance(path, list) else [],
                "screen_title": scr.get("screen_title"),
                "description": f"界面深度 {scr.get('depth', 0)}；路径 {path_label}",
                "location": path_label,
                "children": [],
            }
            for fid in scr.get("feature_ids") or []:
                feat = feat_by_id.get(str(fid))
                if feat:
                    screen_node["children"].append(
                        {
                            "id": feat.get("id"),
                            "name": feat.get("name"),
                            "node_type": "function",
                            "depth": feat.get("depth"),
                            "path": feat.get("path"),
                            "function_type": feat.get("function_type"),
                            "description": feat.get("description"),
                            "location": feat.get("location"),
                            "screen_title": feat.get("screen_title"),
                            "region": feat.get("region"),
                            "status": feat.get("status"),
                            "feature_id": feat.get("id"),
                            "children": [],
                        }
                    )
            if screen_node["children"]:
                root["children"].append(screen_node)
        tree["function_tree"] = root if root["children"] else tree["function_tree_by_path"]
    else:
        tree["function_tree"] = tree["function_tree_by_path"]
    tree.setdefault("screens", [])
    return tree
