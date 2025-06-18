from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String)
    free_requests_left = Column(Integer, default=5)
    last_request_date = Column(Date)
    is_subscribed = Column(Boolean, default=False)
    subscription_expiry = Column(Date)


class Database:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def user_exists(self, user_id):
        session = self.Session()
        exists = session.query(User).filter_by(id=user_id).first() is not None
        session.close()
        return exists

    def add_user(self, user_id, **kwargs):
        session = self.Session()
        user = User(id=user_id, **kwargs)
        session.add(user)
        session.commit()
        session.close()

    def get_user(self, user_id):
        session = self.Session()
        user = session.query(User).filter_by(id=user_id).first()
        session.close()
        return user if user else None

    def update_user(self, user_id, updates):
        session = self.Session()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            for key, value in updates.items():
                setattr(user, key, value)
            session.commit()
        session.close()