from db import DB_NAME
import aiosqlite

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chat_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def update_inventory(new_data: dict):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT product_name, quantity FROM inventory") as cursor:
            rows = await cursor.fetchall()

        old_data = {name: qty for name, qty in rows}

        for product, new_qty in new_data.items():
            old_qty = old_data.get(product, 0)

            # продаж
            if new_qty < old_qty:
                sold = old_qty - new_qty

                async with db.execute(
                    "SELECT price FROM products WHERE name=?",
                    (product,)
                ) as cursor:
                    row = await cursor.fetchone()
                    price = row[0] if row else 0

                await db.execute(
                    "INSERT INTO sales (product_name, quantity, total_price) VALUES (?, ?, ?)",
                    (product, sold, sold * price)
                )

            # оновлення складу
            await db.execute(
                "INSERT OR REPLACE INTO inventory (product_name, quantity) VALUES (?, ?)",
                (product, new_qty)
            )

        await db.commit()


async def get_warehouse():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT product_name, quantity FROM warehouse") as cursor:
            return await cursor.fetchall()

async def add_item_to_warehouse(name: str, qty: int, price: float):
    async with aiosqlite.connect(DB_NAME) as db:                
        await db.execute("""
            INSERT INTO warehouse (product_name, quantity)
            VALUES (?, ?)
            ON CONFLICT(product_name)
            DO UPDATE SET quantity = quantity + excluded.quantity
        """, (name, qty))

        await db.commit()

async def get_shelf():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT product_name, quantity FROM shelf") as cursor:
            return await cursor.fetchall()
        

async def move_to_shelf(product_name, qty):
    async with aiosqlite.connect(DB_NAME) as db:
        # перевіряємо склад
        async with db.execute(
            "SELECT quantity FROM warehouse WHERE product_name=?",
            (product_name,)
        ) as cur:
            row = await cur.fetchone()

        if not row or row[0] < qty:
            return False

        # зменшуємо склад
        await db.execute("""
            UPDATE warehouse
            SET quantity = quantity - ?
            WHERE product_name = ?
        """, (qty, product_name))

        # додаємо на вітрину
        await db.execute("""
            INSERT INTO shelf (product_name, quantity)
            VALUES (?, ?)
            ON CONFLICT(product_name)
            DO UPDATE SET quantity = quantity + excluded.quantity
        """, (product_name, qty))

        await db.commit()
        return True


async def update_shelf_from_ai(detected: dict):
    async with aiosqlite.connect(DB_NAME) as db:
        for product, new_qty in detected.items():

            # отримати старий стан
            async with db.execute(
                "SELECT quantity FROM shelf WHERE product_name=?",
                (product,)
            ) as cur:
                row = await cur.fetchone()
                old_qty = row[0] if row else 0

            diff = old_qty - new_qty

            if diff > 0:
                # продаж
                async with db.execute(
                    "SELECT price FROM products WHERE name=?",
                    (product,)
                ) as cur:
                    price_row = await cur.fetchone()
                    price = price_row[0] if price_row else 0

                await db.execute("""
                    INSERT INTO sales (product_name, quantity, total_price)
                    VALUES (?, ?, ?)
                """, (product, diff, diff * price))

            # оновити вітрину
            await db.execute("""
                INSERT INTO shelf (product_name, quantity)
                VALUES (?, ?)
                ON CONFLICT(product_name)
                DO UPDATE SET quantity = excluded.quantity
            """, (product, new_qty))

        await db.commit()


async def get_sales_today():

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT SUM(quantity), SUM(total_price)
            FROM sales
            WHERE date(created_at) = date('now')
        """) as cursor:
            return await cursor.fetchone()
        

