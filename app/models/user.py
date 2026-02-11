from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.models.db import Base, engine


class User(Base):
    __tablename__ = "user_details"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)


def init_db():
    """Create tables and insert test data if not present."""

    Base.metadata.create_all(bind=engine)

    from app.models.db import SessionLocal

    db = SessionLocal()
    try:
        test_username = "admin"
        test_password_hash = "root"  # TODO: replace with proper hashing

        user = db.query(User).filter_by(user_name=test_username).first()
        if user is None:
            user = User(
                user_name=test_username,
                email="admin@example.com",
                full_name="System Administrator",
                password_hash=test_password_hash,
                role="admin",
                is_active=True,
                is_email_verified=False,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()
