from sqlalchemy import text
from connection.db import create_source_sessionmaker

# Debugging purposes only

Session = create_source_sessionmaker()

with Session() as session:
    total = session.scalar(text("SELECT COUNT(*) FROM film"))
    print(total)  # should print 1000
