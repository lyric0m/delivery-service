import httpx
import os
from typing import Optional, Dict, List
from decimal import Decimal

CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:8002")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8004")

async def check_product_availability(product_id: int, darkstore_id: int, quantity: int) -> bool:
    """Проверка доступности товара в дарксторе через catalog-service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CATALOG_SERVICE_URL}/inventory/{product_id}/{darkstore_id}/check",
                params={"quantity": quantity},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("available", False)
            return False
    except Exception as e:
        print(f"Error checking product availability: {e}")
        return False

async def get_product_info(product_id: int) -> Optional[Dict]:
    """Получение информации о товаре через catalog-service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CATALOG_SERVICE_URL}/products/{product_id}",
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
            return None
    except Exception as e:
        print(f"Error getting product info: {e}")
        return None

async def check_products_availability(items: List[Dict], darkstore_id: int):
    """
    Проверка доступности всех товаров в заказе
    Возвращает (is_available, error_message)
    """
    for item in items:
        product_id = item["product_id"]
        quantity = item["quantity"]
        
        is_available = await check_product_availability(product_id, darkstore_id, quantity)
        if not is_available:
            product_info = await get_product_info(product_id)
            product_name = product_info.get("name", f"Product {product_id}") if product_info else f"Product {product_id}"
            return False, f"Недостаточно товара '{product_name}' (ID: {product_id}) в дарксторе"
    
    return True, None

async def process_payment(order_id: int, amount: Decimal) -> tuple:
    """
    Обработка платежа через payment-service
    Возвращает (success, payment_id или error_message)
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYMENT_SERVICE_URL}/payments",
                json={
                    "order_id": order_id,
                    "amount": float(amount)
                },
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                return True, data.get("payment_id")
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get("detail", "Payment failed")
                return False, error_message
    except httpx.TimeoutException:
        return False, "Payment service timeout"
    except Exception as e:
        print(f"Error processing payment: {e}")
        return False, f"Payment service error: {str(e)}"

async def reserve_products(items: List[Dict], darkstore_id: int) -> bool:
    """
    Резервирование товаров (уменьшение остатков) через catalog-service
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CATALOG_SERVICE_URL}/internal/inventory/reserve",
                json={
                    "items": items,
                    "darkstore_id": darkstore_id
                },
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                # Проверяем, что все товары успешно зарезервированы
                results = data.get("results", [])
                all_success = all(result.get("success", False) for result in results)
                if not all_success:
                    failed_items = [r for r in results if not r.get("success")]
                    print(f"Warning: Some items failed to reserve: {failed_items}")
                return all_success
            else:
                error_data = response.json() if response.content else {}
                print(f"Error reserving products: {response.status_code}, {error_data}")
                return False
    except Exception as e:
        print(f"Error reserving products: {e}")
        return False

async def release_products(items: List[Dict], darkstore_id: int) -> bool:
    """
    Освобождение товаров (возврат остатков при отмене заказа) через catalog-service
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CATALOG_SERVICE_URL}/internal/inventory/release",
                json={
                    "items": items,
                    "darkstore_id": darkstore_id
                },
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                # Проверяем, что все товары успешно освобождены
                results = data.get("results", [])
                all_success = all(result.get("success", False) for result in results)
                if not all_success:
                    failed_items = [r for r in results if not r.get("success")]
                    print(f"Warning: Some items failed to release: {failed_items}")
                return all_success
            else:
                error_data = response.json() if response.content else {}
                print(f"Error releasing products: {response.status_code}, {error_data}")
                return False
    except Exception as e:
        print(f"Error releasing products: {e}")
        return False
