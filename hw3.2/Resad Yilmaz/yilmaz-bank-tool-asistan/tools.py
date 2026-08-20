import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

import database as db


# ============================================================
# GİRDİ ŞEMALARI
# ============================================================

class FindUserByNameInput(BaseModel):
    name: str = Field(..., min_length=2, description="Aranacak kişinin adı veya adı+soyadı (kısmi eşleşme de olur)")


class ListAccountsInput(BaseModel):
    user_id: int = Field(..., description="Hesapları listelenecek kullanıcının id'si")


class OpenNewAccountInput(BaseModel):
    user_id: int = Field(..., description="Hesabın açılacağı kullanıcının id'si")
    account_type: str = Field(..., description="Hesap tipi: vadesiz, vadeli veya tasarruf")
    currency: str = Field(default="TRY", description="Para birimi: TRY, EUR veya USD")


class GetBalanceInput(BaseModel):
    account_id: int = Field(..., description="Bakiyesi sorgulanacak hesabın id'si")


class GetTransactionHistoryInput(BaseModel):
    account_id: int = Field(..., description="İşlem geçmişi sorgulanacak hesabın id'si")
    limit: int = Field(default=10, ge=1, le=50, description="Döndürülecek maksimum işlem sayısı")


class TransferMoneyInput(BaseModel):
    from_account_id: int = Field(..., description="Parayı gönderen hesabın id'si")
    to_account_id: int = Field(..., description="Parayı alan hesabın id'si")
    amount: float = Field(..., gt=0, description="Transfer edilecek tutar (pozitif olmalı)")
    description: str = Field(default="", description="Transfer açıklaması (opsiyonel)")


class ExchangeTransferInput(BaseModel):
    from_account_id: int = Field(..., description="Parayı gönderen hesabın id'si")
    to_account_id: int = Field(..., description="Parayı alan hesabın id'si (farklı para biriminde olmalı)")
    amount: float = Field(..., gt=0, description="Gönderen hesabın para biriminden, transfer edilecek tutar")
    description: str = Field(default="", description="Transfer açıklaması (opsiyonel)")


class CreateCardInput(BaseModel):
    account_id: int = Field(..., description="Kartın bağlanacağı hesabın id'si")
    card_type: str = Field(..., description="Kart tipi: debit, credit veya virtual")


class BlockCardInput(BaseModel):
    card_id: int = Field(..., description="Bloke edilecek kartın id'si")


# ============================================================
# TOOL FONKSİYONLARI — bağlantıyı kendileri açar/kapatır, yazma
# işlemlerinde commit/rollback kendileri yönetir
# ============================================================

def find_user_by_name(name: str) -> dict:
    conn = db.get_connection()
    try:
        users = db.find_users_by_name(conn, name=name)
        return {"query": name, "users": users, "count": len(users)}
    finally:
        conn.close()


def list_accounts(user_id: int) -> dict:
    conn = db.get_connection()
    try:
        accounts = db.list_accounts(conn, user_id=user_id)
        return {"user_id": user_id, "accounts": accounts, "count": len(accounts)}
    finally:
        conn.close()


def open_new_account(user_id: int, account_type: str, currency: str = "TRY") -> dict:
    conn = db.get_connection()
    try:
        result = db.open_new_account(conn, user_id=user_id, account_type=account_type, currency=currency)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_balance(account_id: int) -> dict:
    conn = db.get_connection()
    try:
        balance = db.get_balance(conn, account_id=account_id)
        if balance is None:
            raise ValueError(f"Hesap bulunamadı: {account_id}")
        return balance
    finally:
        conn.close()


def get_transaction_history(account_id: int, limit: int = 10) -> dict:
    conn = db.get_connection()
    try:
        account = db.get_account(conn, account_id=account_id)
        if account is None:
            raise ValueError(f"Hesap bulunamadı: {account_id}")
        history = db.get_transaction_history(conn, account_id=account_id, limit=limit)
        return {"account_id": account_id, "transactions": history, "count": len(history)}
    finally:
        conn.close()


def transfer_money(from_account_id: int, to_account_id: int, amount: float, description: str = "") -> dict:
    conn = db.get_connection()
    try:
        result = db.transfer_money(
            conn, from_account_id=from_account_id, to_account_id=to_account_id,
            amount=amount, description=description,
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def exchange_transfer(from_account_id: int, to_account_id: int, amount: float, description: str = "") -> dict:
    conn = db.get_connection()
    try:
        result = db.exchange_transfer(
            conn, from_account_id=from_account_id, to_account_id=to_account_id,
            amount=amount, description=description,
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_card(account_id: int, card_type: str) -> dict:
    conn = db.get_connection()
    try:
        result = db.create_card(conn, account_id=account_id, card_type=card_type)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def block_card(card_id: int) -> dict:
    conn = db.get_connection()
    try:
        result = db.block_card(conn, card_id=card_id)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# TOOL ŞEMALARI (LLM'e gönderilecek JSON tanımları)
# ============================================================

def create_tool_schema(name: str, description: str, input_model: type[BaseModel]) -> dict:
    parameters = input_model.model_json_schema()
    parameters.pop("title", None)
    parameters["additionalProperties"] = False

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


TOOLS = [
    create_tool_schema(
        name="find_user_by_name",
        description="Bir kişiyi ad/soyad ile arar, eşleşen kullanıcıların user_id'sini döner. İsimle ilgili her istekte İLK ÖNCE bu çağrılmalıdır.",
        input_model=FindUserByNameInput,
    ),
    create_tool_schema(
        name="list_accounts",
        description="Bir kullanıcıya ait tüm hesapları listeler (hesap numarası, tipi, bakiyesi).",
        input_model=ListAccountsInput,
    ),
    create_tool_schema(
        name="open_new_account",
        description="Bir kullanıcı için yeni bir banka hesabı açar (0 bakiye ile başlar). Hesap numarası otomatik üretilir.",
        input_model=OpenNewAccountInput,
    ),
    create_tool_schema(
        name="get_balance",
        description="Belirli bir hesabın güncel bakiyesini getirir.",
        input_model=GetBalanceInput,
    ),
    create_tool_schema(
        name="get_transaction_history",
        description="Belirli bir hesabın son işlemlerini (para yatırma, çekme, transfer) getirir.",
        input_model=GetTransactionHistoryInput,
    ),
    create_tool_schema(
        name="transfer_money",
        description="AYNI para birimindeki iki hesap arasında transfer yapar. Para birimleri farklıysa bunun yerine exchange_transfer kullanılmalıdır.",
        input_model=TransferMoneyInput,
    ),
    create_tool_schema(
        name="exchange_transfer",
        description="FARKLI para birimindeki iki hesap arasında, sabit demo döviz kuruyla transfer yapar (ör. TRY hesaptan EUR hesaba). İki hesap aynı para biriminde ise bunun yerine transfer_money kullanılmalıdır.",
        input_model=ExchangeTransferInput,
    ),
    create_tool_schema(
        name="create_card",
        description="Bir hesaba yeni kart (debit, credit veya virtual) oluşturur.",
        input_model=CreateCardInput,
    ),
    create_tool_schema(
        name="block_card",
        description="Belirli bir kartı bloke eder (kayıp/çalıntı durumunda kullanılır).",
        input_model=BlockCardInput,
    ),
]


TOOL_REGISTRY = {
    "find_user_by_name": find_user_by_name,
    "list_accounts": list_accounts,
    "open_new_account": open_new_account,
    "get_balance": get_balance,
    "get_transaction_history": get_transaction_history,
    "transfer_money": transfer_money,
    "exchange_transfer": exchange_transfer,
    "create_card": create_card,
    "block_card": block_card,
}

TOOL_INPUT_MODELS = {
    "find_user_by_name": FindUserByNameInput,
    "list_accounts": ListAccountsInput,
    "open_new_account": OpenNewAccountInput,
    "get_balance": GetBalanceInput,
    "get_transaction_history": GetTransactionHistoryInput,
    "transfer_money": TransferMoneyInput,
    "exchange_transfer": ExchangeTransferInput,
    "create_card": CreateCardInput,
    "block_card": BlockCardInput,
}


def execute_tool(tool_name: str, arguments: Any) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {
            "success": False, "tool_name": tool_name, "arguments": arguments,
            "result": None, "error": f"Bilinmeyen tool: {tool_name}",
        }

    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if not isinstance(arguments, dict):
            raise TypeError("Tool argümanları sözlük formatında olmalıdır.")
    except (json.JSONDecodeError, TypeError) as error:
        return {
            "success": False, "tool_name": tool_name, "arguments": arguments,
            "result": None, "error": f"Argüman formatı hatası: {error}",
        }

    input_model = TOOL_INPUT_MODELS[tool_name]

    try:
        validated_input = input_model.model_validate(arguments)
        validated_arguments = validated_input.model_dump()
    except ValidationError as error:
        return {
            "success": False, "tool_name": tool_name, "arguments": arguments,
            "result": None, "error": error.errors(),
        }

    try:
        result = TOOL_REGISTRY[tool_name](**validated_arguments)
        return {
            "success": True, "tool_name": tool_name, "arguments": validated_arguments,
            "result": result, "error": None,
        }
    except Exception as error:
        return {
            "success": False, "tool_name": tool_name, "arguments": validated_arguments,
            "result": None, "error": str(error),
        }