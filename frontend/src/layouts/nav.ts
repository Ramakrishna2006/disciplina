import {
  ActivityIcon,
  CircleQuestionMarkIcon,
  DatabaseIcon,
  FlaskConicalIcon,
  GitCompareIcon,
  LayoutDashboardIcon,
  MessageSquareIcon,
  TypeIcon,
  WaypointsIcon,
  type LucideIcon,
} from "lucide-react"

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  ready: boolean // false: shown, but disabled with a note, until its stage is built
}

// The order of the sidebar (plan, section 10). Pages turn on one by one in stage 5.
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/app", icon: LayoutDashboardIcon, ready: true },
  { label: "Playground", to: "/app/playground", icon: MessageSquareIcon, ready: false },
  { label: "Tokenizer", to: "/app/tokenizer", icon: TypeIcon, ready: false },
  { label: "Embeddings", to: "/app/embeddings", icon: WaypointsIcon, ready: false },
  { label: "Dataset", to: "/app/dataset", icon: DatabaseIcon, ready: false },
  { label: "Experiments", to: "/app/experiments", icon: FlaskConicalIcon, ready: false },
  { label: "Compare", to: "/app/compare", icon: GitCompareIcon, ready: false },
  { label: "Activity", to: "/app/activity", icon: ActivityIcon, ready: false },
  { label: "Help", to: "/app/help", icon: CircleQuestionMarkIcon, ready: false },
]
