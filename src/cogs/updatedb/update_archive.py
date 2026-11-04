from chickensmoothie import Client, Pet
from chickensmoothie.archive import ArchiveEvent, TableType


async def process_event(
    client: Client, conn, event: ArchiveEvent, table: TableType, year: int
) -> tuple[int, int]:
    page = await client.get_archive_event(event, table, year)
    for entry in page.entries:
        if isinstance(entry, Pet):
            await conn.execute(
                "INSERT OR REPLACE INTO Pets (petID, petYear, petEvent, petLink) VALUES (?, ?, ?, ?)",
                (entry.id, entry.year, entry.event, entry.archive_url),
            )
        else:
            await conn.execute(
                "INSERT OR REPLACE INTO Items (itemLID, itemRID, itemName, itemYear, itemEvent, itemLink) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry.left_id,
                    entry.right_id,
                    entry.name,
                    entry.year,
                    entry.event,
                    entry.archive_url,
                ),
            )
    return page.group_count, len(page.entries)
