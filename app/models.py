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


# --- Trips ---


class TripCreate(BaseModel):
    title: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    participants: list[int] | None = None


class TripUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    participants: list[int] | None = None


class TripResponse(BaseModel):
    id: int
    title: str
    description: str | None
    start_date: str | None
    end_date: str | None
    participants: list[int] | None
    created_at: str
    updated_at: str


# --- Expenses ---


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    tag: str | None = None
    category: str | None = None
    location: str | None = None
    description: str | None = None
    payor_id: int | None = None
    participants: list[int] | None = None
    trip_id: int | None = None


class ExpenseUpdate(BaseModel):
    title: str | None = None
    amount: float | None = None
    tag: str | None = None
    category: str | None = None
    location: str | None = None
    description: str | None = None
    payor_id: int | None = None
    participants: list[int] | None = None
    trip_id: int | None = None


class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: float
    tag: str | None
    category: str | None
    location: str | None
    description: str | None
    payor_id: int | None
    participants: list[int] | None
    trip_id: int | None
    created_at: str
    updated_at: str


# --- Organizations ---


class OrganizationCreate(BaseModel):
    name: str


class OrganizationUpdate(BaseModel):
    name: str | None = None


class OrganizationResponse(BaseModel):
    id: int
    name: str
    created_at: str
    updated_at: str


# --- Projects ---


class ProjectCreate(BaseModel):
    title: str
    description: str | None = None
    status: str | None = "active"
    organization_id: int


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    organization_id: int | None = None


class ProjectResponse(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    created_at: str
    updated_at: str
    owner_id: int | None
    organization_id: int | None


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


# --- Invites ---


class InviteCreate(BaseModel):
    code: str | None = None
    max_uses: int = 1


class InviteResponse(BaseModel):
    id: int
    code: str
    max_uses: int
    uses: int
    created_at: str


# --- Users ---


class UserRegister(BaseModel):
    email: str
    password: str
    organization_id: int | None = None
    invite_code: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    organization_id: int | None
    created_at: str


class LoginResponse(BaseModel):
    api_key: str
    expires_at: str
