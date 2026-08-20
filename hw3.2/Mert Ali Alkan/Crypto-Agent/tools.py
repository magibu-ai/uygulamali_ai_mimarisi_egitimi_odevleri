import requests
import json
from db import get_portfolio, execute_trade

def get_crypto_price(symbol: str):
    """
    Binance.US üzerinden güncel kripto fiyatını çeker.
    """
    symbol = symbol.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
        
    url = f"https://api.binance.us/api/v3/ticker/price?symbol={symbol}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if 'price' in data:
            return float(data['price'])
        return f"Hata: {symbol} fiyatı bulunamadı."
    except Exception as e:
        return f"API Hatası: {str(e)}"

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Belirtilen kripto paranın anlık güncel fiyatını (USD) getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Kripto para sembolü. Örn: BTC, ETH"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "Kullanıcının cüzdanındaki mevcut USDT ve kripto varlıkları getirir.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_trade",
            "description": "Kripto alım veya satım işlemi gerçekleştirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["buy", "sell"],
                        "description": "İşlem türü ('buy' veya 'sell')."
                    },
                    "symbol": {
                        "type": "string",
                        "description": "İşlem yapılacak kripto paranın sembolü (Örn: BTC)."
                    },
                    "usdt_amount": {
                        "type": "number",
                        "description": "İşleme ayrılacak toplam USD tutarı (Sadece USD cinsinden miktar biliniyorsa kullanılır)."
                    },
                    "amount": {
                        "type": "number",
                        "description": "İşlem yapılacak kripto miktarı (Sadece kripto miktarı biliniyorsa kullanılır)."
                    },
                    "price": {
                        "type": "number",
                        "description": "İşlemin gerçekleştirileceği anlık birim fiyat (get_crypto_price'dan alınmalıdır)."
                    }
                },
                "required": ["action", "symbol", "price"]
            }
        }
    }
]

def handle_tool_call(name, arguments):
    """LLM araç çağrılarını yönlendirir ve çalıştırır."""
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
        
    if name == "get_crypto_price":
        return str(get_crypto_price(arguments.get("symbol")))
    elif name == "get_portfolio":
        return json.dumps(get_portfolio())
    elif name == "execute_trade":
        price = float(arguments.get("price"))
        usdt_amount = arguments.get("usdt_amount")
        amount = arguments.get("amount")
        
        # Miktar hesaplama (USDT verilmişse coin miktarını otomatik hesapla)
        if usdt_amount and price > 0:
            calculated_amount = float(usdt_amount) / price
        elif amount:
            calculated_amount = float(amount)
        else:
            return "Hata: usdt_amount veya amount belirtilmelidir."
            
        result = execute_trade(
            action=arguments.get("action"),
            symbol=arguments.get("symbol").upper().replace("USDT", ""),
            amount=calculated_amount,
            price=price
        )
        return json.dumps(result, ensure_ascii=False)
    else:
        return "Hata: Bilinmeyen fonksiyon."
