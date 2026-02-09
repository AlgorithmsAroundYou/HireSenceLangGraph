from sqlalchemy import Boolean, Column, Integer, String

from app.models.db import Base, engine


class User(Base):
    __tablename__ = "user_details"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


def init_db():
    """Create tables and insert test data if not present."""

    Base.metadata.create_all(bind=engine)

    from app.models.db import SessionLocal

    db = SessionLocal()
    try:
        # simple "encrypted" placeholder as requested
        test_username = "saikodati"
        test_password = "root"  # replace with proper hashing later

        user = db.query(User).filter_by(user_name=test_username).first()
        if user is None:
            user = User(
                user_name=test_username,
                password=test_password,
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()
