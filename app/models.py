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


# --- Projects ---


class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    status: str | None = "active"


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    created_at: str
    updated_at: str


# --- Epics ---


class EpicCreate(BaseModel):
    title: str
    description: str | None = None
    status: str | None = "active"


class EpicUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class EpicResponse(BaseModel):
    id: int
    project_id: int
    title: str
    description: str | None
    status: str
    created_at: str
    updated_at: str


# --- Tasks ---


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    deadline: str | None = None
    status: str | None = "todo"
    label: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    deadline: str | None = None
    status: str | None = None
    label: str | None = None


class TaskResponse(BaseModel):
    id: int
    epic_id: int
    title: str
    description: str | None
    deadline: str | None
    status: str
    label: str | None
    created_at: str
    updated_at: str
