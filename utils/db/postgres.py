from typing import Optional, Union, List
import asyncpg
from asyncpg import Connection, Pool
from data import config


class Database:
    def __init__(self):
        self.pool: Optional[Pool] = None

    async def create(self):
        """PostgreSQL bilan ulanishni yaratish."""
        self.pool = await asyncpg.create_pool(
            user=config.DB_USER,
            password=config.DB_PASS,
            host=config.DB_HOST,
            database=config.DB_NAME,
            port=config.DB_PORT
        )

    async def execute(
        self,
        command: str,
        *args,
        fetch: bool = False,
        fetchval: bool = False,
        fetchrow: bool = False,
        execute: bool = False,
    ) -> Union[List[asyncpg.Record], asyncpg.Record, str, int, None]:
        """SQL buyruqlarini bajarish."""
        if self.pool is None:
            raise ConnectionError("Database pool is not initialized!")

        async with self.pool.acquire() as connection:
            connection: Connection
            async with connection.transaction():
                if fetch:
                    return await connection.fetch(command, *args)
                elif fetchval:
                    return await connection.fetchval(command, *args)
                elif fetchrow:
                    return await connection.fetchrow(command, *args)
                elif execute:
                    return await connection.execute(command, *args)
        return None

    async def create_table_users(self):
        """Foydalanuvchilar jadvalini yaratish."""
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            username VARCHAR(255),
            telegram_id BIGINT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            language VARCHAR(255) NOT NULL
        );
        """
        await self.execute(sql, execute=True)

    @staticmethod
    def format_args(parameters: dict) -> tuple[str, tuple]:
        """SQL argumentlarini formatlash."""
        # Argumentlarni to'g'ri formatlash
        sql = "SELECT * FROM users WHERE " + " AND ".join(
            [f"{key} = ${i}" for i, key in enumerate(parameters.keys(), start=1)]
        )
        return sql, tuple(parameters.values())
    
    async def add_user(self, full_name: str, username: Optional[str], telegram_id: int, language: Optional[str]):
        """Yangi foydalanuvchini qo‘shish."""
        sql = """
        INSERT INTO users (full_name, username, telegram_id, language) 
        VALUES ($1, $2, $3, $4) RETURNING *;
        """
        return await self.execute(sql, full_name, username, telegram_id, language, fetchrow=True)

    async def select_all_users(self):
        """Barcha foydalanuvchilarni olish."""
        sql = "SELECT * FROM users"
        return await self.execute(sql, fetch=True)

    async def select_user(self, **kwargs):
        """Bitta foydalanuvchini olish."""
        sql, parameters = self.format_args(kwargs)
        return await self.execute(sql, *parameters, fetchrow=True)

    async def is_user_exists(self, telegram_id: int) -> bool:
        """Foydalanuvchi mavjudligini tekshirish."""
        sql = "SELECT EXISTS(SELECT 1 FROM users WHERE telegram_id = $1)"
        return await self.execute(sql, telegram_id, fetchval=True)

    async def update_user_language(self, telegram_id: int, language: str):
        """Foydalanuvchining tilini yangilash."""
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE users SET language = $1 WHERE telegram_id = $2",
                language, telegram_id
            )

    async def count_users(self):
        """Jami foydalanuvchilar sonini olish."""
        sql = "SELECT COUNT(*) FROM users"
        return await self.execute(sql, fetchval=True)

    async def update_user_username(self, username: str, telegram_id: int):
        """Foydalanuvchi username'ini yangilash."""
        sql = "UPDATE users SET username=$1 WHERE telegram_id=$2"
        return await self.execute(sql, username, telegram_id, execute=True)

    async def delete_users(self):
        """Barcha foydalanuvchilarni o‘chirish."""
        await self.execute("DELETE FROM users WHERE TRUE", execute=True)

    async def drop_users(self):
        """Foydalanuvchilar jadvalini o‘chirish."""
        await self.execute("DROP TABLE users", execute=True)