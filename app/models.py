from pydantic import BaseModel


# --- Todos ---


class TodoCreate(BaseModel):
    title: str
    description: str | None = None


class TodoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None


class TodoResponse(BaseModel):
    id: int
    title: str
    description: str | None
    completed: bool
    created_at: str
    updated_at: str


# --- RAG ---


class DocumentIngestRequest(BaseModel):
    content: str
    title: str | None = "Untitled"


class DocumentIngestResponse(BaseModel):
    document_id: int
    chunks_created: int
    message: str


class RAGQueryRequest(BaseModel):
    question: str
    document_id: int | None = None


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[str]


# --- Expenses ---


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    tag: str | None = None
    category: str | None = None
    location: str | None = None
    description: str | None = None
    paid_by: str
    shared_with: list[str] | None = None


class ExpenseUpdate(BaseModel):
    title: str | None = None
    amount: float | None = None
    tag: str | None = None
    category: str | None = None
    location: str | None = None
    description: str | None = None
    paid_by: str | None = None
    shared_with: list[str] | None = None


class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: float
    tag: str | None
    category: str | None
    location: str | None
    description: str | None
    paid_by: str
    shared_with: list[str] | None
    created_at: str
    updated_at: str
