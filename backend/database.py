from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import List, Optional
from datetime import datetime

class Interaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    user_text: str
    ai_response: str
    audio_url: Optional[str] = None 
    image_path: Optional[str] = None

sqlite_url = "sqlite:///synapse_v.db"
engine = create_engine(sqlite_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def save_interaction(u_text, ai_res, a_url=None, i_path=None):
    with Session(engine) as session:
        new_entry = Interaction(user_text=u_text, ai_response=ai_res, audio_url=a_url, image_path=i_path)
        session.add(new_entry)
        session.commit()
        session.refresh(new_entry)
        return new_entry.id

def update_interaction(item_id: int, u_text: str, ai_res: str, a_url: str):
    with Session(engine) as session:
        statement = select(Interaction).where(Interaction.id == item_id)
        item = session.exec(statement).one_or_none()
        if item:
            item.user_text, item.ai_response, item.audio_url = u_text, ai_res, a_url
            session.add(item); session.commit(); session.refresh(item)
            return item.id
        return None

def get_all_history():
    with Session(engine) as session: return session.exec(select(Interaction)).all()

def delete_all_history():
    with Session(engine) as session:
        for item in session.exec(select(Interaction)).all(): session.delete(item)
        session.commit()

def delete_specific_interaction(item_id: int):
    with Session(engine) as session:
        item = session.exec(select(Interaction).where(Interaction.id == item_id)).one_or_none()
        if item: session.delete(item); session.commit()