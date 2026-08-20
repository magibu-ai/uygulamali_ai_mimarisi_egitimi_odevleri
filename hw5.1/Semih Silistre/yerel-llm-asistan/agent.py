"""
Araç çağırma döngüsü.

Akış:
  kullanıcı mesajı → model → (araç çağrısı var mı?)
      evet → araçları çalıştır, sonuçları geçmişe ekle, modele geri dön
      hayır → cevabı döndür

Döngü `MAX_TOOL_ROUNDS` turla sınırlı; model kendini araç çağırmaya kilitlerse
elde olan bilgiyle cevaplamaya zorlanır.
"""

from __future__ import annotations

import re

from openai import OpenAI

from config import (
    API_KEY,
    BASE_URL,
    MAX_HISTORY_MESSAGES,
    MAX_TOKENS,
    MAX_TOOL_ROUNDS,
    MODEL,
    TEMPERATURE,
)
from system_prompt import build_system_prompt
from tools import TOOL_FUNCS, TOOL_SCHEMAS, execute_tool

# Model bazen aracı gerçekten çağırmak yerine cevabın içine `calculator("2+2")`
# gibi sahte bir çağrı yazıp sonucunu uyduruyor. Bu kalıp onu yakalar.
_SAHTE_CAGRI = re.compile(r"\b(" + "|".join(TOOL_FUNCS) + r")\s*\(\s*[\"'{]")


class Agent:
    def __init__(self, verbose: bool = True):
        self.client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
        self.verbose = verbose
        self.system_message = {"role": "system", "content": build_system_prompt()}
        self.history: list[dict] = []
        self._duzeltme_yapildi = False

    # -- yardımcılar ---------------------------------------------------------
    def _log(self, text: str) -> None:
        if self.verbose:
            print(text)

    def _messages(self) -> list[dict]:
        """System + kırpılmış geçmiş."""
        return [self.system_message, *self.history[-MAX_HISTORY_MESSAGES:]]

    def _complete(self):
        return self.client.chat.completions.create(
            model=MODEL,
            messages=self._messages(),
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

    def reset(self) -> None:
        self.history.clear()
        self._duzeltme_yapildi = False

    # -- ana döngü -----------------------------------------------------------
    def ask(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})
        self._duzeltme_yapildi = False

        for round_no in range(1, MAX_TOOL_ROUNDS + 1):
            try:
                response = self._complete()
            except Exception as exc:
                return (
                    f"Modele ulaşılamadı: {exc}\n"
                    f"LM Studio sunucusu açık mı? ({BASE_URL}) Model yüklü mü? (`lms ps`)"
                )

            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            # Araç çağrısı yoksa iş bitti — ama önce sahte çağrı kontrolü.
            if not tool_calls:
                answer = (message.content or "").strip()

                # Model aracı çağırmak yerine metne yazmışsa bir kez uyar ve
                # gerçekten çağırmasını iste. Tek sefer; yoksa döngüye girer.
                if _SAHTE_CAGRI.search(answer) and not self._duzeltme_yapildi:
                    self._duzeltme_yapildi = True
                    self._log("  ⚠️  Cevapta sahte araç çağrısı var, gerçek çağrı isteniyor.")
                    self.history.append({"role": "assistant", "content": answer})
                    self.history.append(
                        {
                            "role": "user",
                            "content": (
                                "Cevabında araç çağrısını metin olarak yazmışsın; metne yazılan "
                                "çağrı çalışmaz ve sonucu uydurmuş olursun. Aracı gerçekten çağır, "
                                "dönen değeri kullanarak cevabı yeniden yaz."
                            ),
                        }
                    )
                    continue

                self.history.append({"role": "assistant", "content": answer})
                return answer or "(model boş cevap döndü)"

            # Asistanın araç çağrısı içeren mesajı geçmişe aynen eklenmeli.
            self.history.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                name = tc.function.name
                args = tc.function.arguments
                self._log(f"  🔧 [{round_no}] {name}({args})")

                result = execute_tool(name, args)
                preview = result.replace("\n", " ")[:160]
                self._log(f"  ↩️  {preview}{'…' if len(result) > 160 else ''}")

                self.history.append(
                    {"role": "tool", "tool_call_id": tc.id, "name": name, "content": result}
                )

        # Tur limiti doldu: araçsız son bir deneme yaptır.
        self._log("  ⚠️  Araç turu limiti doldu, eldeki bilgiyle cevaplanıyor.")
        self.history.append(
            {
                "role": "user",
                "content": "Araç kullanmayı bırak ve şu ana kadar topladığın bilgiyle cevap ver.",
            }
        )
        try:
            final = self.client.chat.completions.create(
                model=MODEL,
                messages=self._messages(),
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
        except Exception as exc:
            return f"Modele ulaşılamadı: {exc}"

        answer = (final.choices[0].message.content or "").strip()
        self.history.append({"role": "assistant", "content": answer})
        return answer or "(model boş cevap döndü)"
