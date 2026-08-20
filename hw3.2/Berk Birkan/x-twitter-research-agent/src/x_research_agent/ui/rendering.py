from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from x_research_agent.tools.runtime import AgentRuntime


def render_report(report: dict[str, Any], runtime: AgentRuntime) -> str:
    post_map = {post.id: post for page in runtime.search_cache.values() for post in page.posts}
    lines = ["## Kısa cevap", report["short_answer"], "", "## Duygu görünümü"]
    lines.extend([report["sentiment_overview"], ""])
    for heading, key in (
        ("Olumlu temalar", "positive_themes"),
        ("Olumsuz temalar", "negative_themes"),
    ):
        lines.append(f"## {heading}")
        themes = report.get(key) or []
        if not themes:
            lines.append("Bu yönde yeterli tema bulunmadı.")
        for theme in themes:
            links = ", ".join(_post_link(pid, post_map) for pid in theme["post_ids"])
            lines.append(f"- **{theme['title']}** — {theme['summary']} ({links})")
        lines.append("")
    lines.extend(
        [
            "## Araştırma sorusunun yanıtı",
            report["answer_to_user_question"],
            "",
            "## Kanıtlar",
        ]
    )
    for evidence in report.get("evidence", []):
        post = post_map.get(evidence["post_id"])
        link = _post_link(evidence["post_id"], post_map)
        excerpt = ""
        if post:
            safe_text = post.text.replace("\n", " ")[:280]
            excerpt = f" — “{safe_text}”"
        lines.append(f"- {link}: {evidence['claim']}{excerpt}")
    lines.extend(["", "## Sınırlamalar"])
    limitations = report.get("limitations") or ["Belirtilmiş ek sınırlama yok."]
    lines.extend(f"- {item}" for item in limitations)
    return "\n".join(lines)


def render_timeline(runtime: AgentRuntime | None, usage: dict[str, Any] | None = None) -> str:
    if runtime is None or not runtime.logs:
        return "Henüz tool çağrısı yok."
    lines = []
    for record in runtime.logs:
        icon = {"succeeded": "✓", "failed": "✗", "cancelled": "■"}.get(record.status, "●")
        duration = f" · {record.duration_ms} ms" if record.duration_ms is not None else ""
        lines.append(
            f"{icon} **{record.sequence}. `{record.tool_name}`**{duration}\n"
            f"  {record.result_summary or 'Çalışıyor...'}"
        )
    lines.append(
        f"\n**Bütçe:** {len(runtime.unique_post_ids)}/"
        f"{runtime.constraints.post_budget} benzersiz gönderi"
    )
    lines.append(f"**Xquik aramaları:** {runtime.search_calls}")
    if usage:
        lines.append(
            f"**OpenRouter:** {usage.get('prompt_tokens', 0)} giriş + "
            f"{usage.get('completion_tokens', 0)} çıkış tokenı · "
            f"bildirilen maliyet ${usage.get('cost', 0):.6f}"
        )
    return "\n\n".join(lines)


def export_report_files(
    *, report: dict[str, Any], runtime: AgentRuntime, export_dir: Path
) -> tuple[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", runtime.thread_id.lower()).strip("-")
    version = runtime.latest_version or 1
    markdown_path = export_dir / f"{slug}-v{version}.md"
    json_path = export_dir / f"{slug}-v{version}.json"
    markdown_path.write_text(render_report(report, runtime), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "thread_id": runtime.thread_id,
                "version": version,
                "report": report,
                "source_posts": [
                    post.model_dump(mode="json")
                    for page in runtime.search_cache.values()
                    for post in page.posts
                    if post.id in {item["post_id"] for item in report.get("evidence", [])}
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(markdown_path), str(json_path)


def _post_link(post_id: str, post_map: dict[str, Any]) -> str:
    post = post_map.get(post_id)
    url = post.url if post else f"https://x.com/i/status/{post_id}"
    return f"[X gönderisi {post_id}]({url})"
