"""Python 侧：从扁平 features 重建 GIIC 层级功能树（与 midscene feature_tree_build 对齐）。"""

from __future__ import annotations

from typing import Any

REGION_TO_FUNCTION_TYPE = {
    "top_tab": "顶部Tab",
    "bottom_tab": "底部Tab",
    "top": "顶部导航",
    "bottom": "底部导航",
    "side": "侧栏",
    "button": "按钮",
    "tab": "Tab",
    "list_item": "列表项",
    "other": "其他控件",
}


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
    loc = str(feat.get("location") or "").strip()
    if not loc:
        feat["location"] = f"{' > '.join(path)} @ {screen}" if screen else " > ".join(path)
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

    enriched = [_enrich_feature(f) for f in features if isinstance(f, dict)]
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


def sync_giic_tree_from_features(tree: dict[str, Any]) -> dict[str, Any]:
    """保存/确认时：始终以 features 为准重建 function_tree，避免与表格编辑不一致。"""
    app_name = str(tree.get("app_name") or "应用")
    features = tree.get("features") or []
    if not isinstance(features, list):
        features = []
    tree["features"] = [_enrich_feature(f) for f in features if isinstance(f, dict)]
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
    tree["features"] = [_enrich_feature(f) for f in features if isinstance(f, dict)]
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
