from __future__ import annotations

from typing import Any

from assistant.action_schema import ActionPlan, ActionType, ResponseMode
from assistant.tool_call_parser import ParsedToolCall


class ResponseFormatter:
    def format_batch(
        self,
        executions: list[tuple[ActionPlan, list[tuple[ParsedToolCall, dict[str, Any]]]]],
    ) -> str:
        sections = [self.format(plan, results) for plan, results in executions]
        return "\n\n".join(section for section in sections if section).strip()

    def format(
        self,
        plan: ActionPlan,
        calls_and_results: list[tuple[ParsedToolCall, dict[str, Any]]],
    ) -> str:
        if not calls_and_results:
            return "İşlem için çalıştırılacak doğrulanmış bir tool bulunamadı."

        failures = [result for _, result in calls_and_results if not result.get("success")]
        successes = [item for item in calls_and_results if item[1].get("success")]
        rendered_success = ""

        if plan.action == ActionType.SEARCH_PRODUCTS and successes:
            rendered_success = self._format_search(successes[0][1])
        elif plan.action == ActionType.GET_PRODUCT_DETAILS and successes:
            rendered_success = "\n\n".join(self._format_product_details(result) for _, result in successes)
        elif plan.action == ActionType.ADD_TO_SHOPPING_LIST and successes:
            rendered_success = "\n\n".join(self._format_add_result(result) for _, result in successes)
        elif plan.action == ActionType.ENSURE_IN_SHOPPING_LIST and successes:
            rendered_success = "\n\n".join(self._format_ensure_result(result) for _, result in successes)
        elif plan.action == ActionType.SET_SHOPPING_LIST_QUANTITY and successes:
            rendered_success = "\n\n".join(self._format_set_result(result) for _, result in successes)
        elif plan.action == ActionType.REMOVE_FROM_SHOPPING_LIST and successes:
            rendered_success = "\n\n".join(self._format_remove_result(result) for _, result in successes)
        elif plan.action in {ActionType.GET_SHOPPING_LIST, ActionType.COUNT_SHOPPING_LIST} and successes:
            result = successes[0][1]
            if plan.response_mode == ResponseMode.COUNT or plan.action == ActionType.COUNT_SHOPPING_LIST:
                rendered_success = self._format_count(result)
            else:
                rendered_success = self._format_shopping_list(result)

        rendered_failures = "\n".join(self._format_error(result) for result in failures)
        return "\n\n".join(section for section in (rendered_success, rendered_failures) if section).strip()

    @staticmethod
    def _format_error(result: dict[str, Any]) -> str:
        code = result.get("error", "UNKNOWN_ERROR")
        messages = {
            "ITEM_NOT_IN_SHOPPING_LIST": "Ürün alışveriş listesinde bulunmuyor",
            "PRODUCT_NOT_FOUND": "Ürün Open Food Facts üzerinde doğrulanamadı",
        }
        message = result.get("message") or messages.get(code) or code
        barcode = result.get("barcode")
        prefix = f"{barcode}: " if barcode else ""
        return f"{prefix}İşlem tamamlanamadı: {message}."

    @staticmethod
    def _format_search(result: dict[str, Any]) -> str:
        products = result.get("products") or []
        if not products:
            return "Arama kriterlerine uygun doğrulanmış ürün bulunamadı."
        lines = ["Open Food Facts üzerinde bulduğum ürünler:"]
        for index, product in enumerate(products, start=1):
            nutriments = product.get("nutriments") or {}
            details = [
                f"Barkod: {product.get('barcode', 'bilinmiyor')}",
                f"Marka: {product.get('brand') or 'bilinmiyor'}",
                f"Nutri-Score: {(product.get('nutrition_grade') or 'bilinmiyor').upper()}",
            ]
            sugars = nutriments.get("sugars_100g")
            kcal = nutriments.get("energy_kcal_100g")
            if sugars is not None:
                details.append(f"Şeker: {sugars:g} g/100 g")
            if kcal is not None:
                details.append(f"Enerji: {kcal:g} kcal/100 g")
            lines.append(f"{index}. **{product.get('name', 'İsimsiz ürün')}** — " + " | ".join(details))
        lines.append("\nVeriler topluluk kaynaklıdır; ambalaj bilgisini ayrıca kontrol et.")
        return "\n".join(lines)

    @staticmethod
    def _format_product_details(result: dict[str, Any]) -> str:
        product = result.get("product") or {}
        nutriments = product.get("nutriments") or {}
        lines = [
            f"**{product.get('name', 'İsimsiz ürün')}**",
            f"- Barkod: {product.get('barcode', 'bilinmiyor')}",
            f"- Marka: {product.get('brand') or 'bilinmiyor'}",
            f"- Nutri-Score: {(product.get('nutrition_grade') or 'bilinmiyor').upper()}",
        ]
        if nutriments.get("sugars_100g") is not None:
            lines.append(f"- Şeker: {nutriments['sugars_100g']:g} g/100 g")
        if nutriments.get("energy_kcal_100g") is not None:
            lines.append(f"- Enerji: {nutriments['energy_kcal_100g']:g} kcal/100 g")
        if product.get("allergens"):
            lines.append("- Alerjen etiketleri: " + ", ".join(product["allergens"]))
        return "\n".join(lines)

    @staticmethod
    def _format_add_result(result: dict[str, Any]) -> str:
        product = result.get("product") or {}
        return (
            f"**{product.get('name', 'Ürün')}** alışveriş listesine eklendi. "
            f"Eklenen miktar: {result.get('added_quantity', 1)}. "
            f"Listedeki toplam miktar: {result.get('quantity', 1)}. "
            f"Barkod: {product.get('barcode', 'bilinmiyor')}."
        )

    @staticmethod
    def _format_ensure_result(result: dict[str, Any]) -> str:
        product = result.get("product") or {}
        if result.get("changed"):
            return (
                f"**{product.get('name', 'Ürün')}** alışveriş listesinde bulunacak şekilde eklendi. "
                f"Listedeki toplam miktar: {result.get('quantity', 1)}. "
                f"Barkod: {product.get('barcode', 'bilinmiyor')}."
            )
        return (
            f"**{product.get('name', 'Ürün')}** zaten alışveriş listesinde. "
            f"Miktar değiştirilmedi: {result.get('quantity', 1)}. "
            f"Barkod: {product.get('barcode', 'bilinmiyor')}."
        )

    @staticmethod
    def _format_set_result(result: dict[str, Any]) -> str:
        product = result.get("product") or {}
        return (
            f"**{product.get('name', 'Ürün')}** miktarı {result.get('quantity', 1)} olarak ayarlandı. "
            f"Önceki miktar: {result.get('previous_quantity') if result.get('previous_quantity') is not None else 0}. "
            f"Barkod: {product.get('barcode', 'bilinmiyor')}."
        )

    @staticmethod
    def _format_remove_result(result: dict[str, Any]) -> str:
        product = result.get("product") or {}
        if result.get("removed_all"):
            return (
                f"**{product.get('name', 'Ürün')}** alışveriş listesinden kaldırıldı. "
                f"Barkod: {product.get('barcode', 'bilinmiyor')}."
            )
        return (
            f"**{product.get('name', 'Ürün')}** için {result.get('removed_quantity', 1)} adet çıkarıldı. "
            f"Kalan miktar: {result.get('quantity', 0)}. "
            f"Barkod: {product.get('barcode', 'bilinmiyor')}."
        )

    @staticmethod
    def _format_shopping_list(result: dict[str, Any]) -> str:
        items = result.get("items") or []
        if not items:
            return "Alışveriş listen şu anda boş."
        lines = ["Alışveriş listen:"]
        total_quantity = 0
        for item in items:
            quantity = int(item.get("quantity", 0))
            total_quantity += quantity
            lines.append(
                f"- **{item.get('product_name', 'İsimsiz ürün')}** — {quantity} adet | "
                f"Barkod: {item.get('barcode', 'bilinmiyor')}"
            )
        lines.append(f"\nToplam: {len(items)} farklı ürün, {total_quantity} adet ürün.")
        return "\n".join(lines)

    @staticmethod
    def _format_count(result: dict[str, Any]) -> str:
        items = result.get("items") or []
        total_quantity = sum(int(item.get("quantity", 0)) for item in items)
        return f"Alışveriş listende {len(items)} farklı ürün ve toplam {total_quantity} adet ürün var."
