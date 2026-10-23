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
  ready: boolean // false: shown, but disabled with a note (for a page that is not built yet)
}

// The order of the sidebar (plan, section 10).
export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/app", icon: LayoutDashboardIcon, ready: true },
  { label: "Playground", to: "/app/playground", icon: MessageSquareIcon, ready: true },
  { label: "Tokenizer", to: "/app/tokenizer", icon: TypeIcon, ready: true },
  { label: "Embeddings", to: "/app/embeddings", icon: WaypointsIcon, ready: true },
  { label: "Dataset", to: "/app/dataset", icon: DatabaseIcon, ready: true },
  { label: "Experiments", to: "/app/experiments", icon: FlaskConicalIcon, ready: true },
  { label: "Compare", to: "/app/compare", icon: GitCompareIcon, ready: true },
  { label: "Activity", to: "/app/activity", icon: ActivityIcon, ready: true },
  { label: "Help", to: "/app/help", icon: CircleQuestionMarkIcon, ready: true },
]
