import {
  ArrowLeft,
  ArrowRight,
  Bell,
  BellOff,
  Calendar,
  CalendarDays,
  Camera,
  Check,
  CircleAlert,
  CircleHelp,
  CircleUserRound,
  CreditCard,
  Download,
  Eye,
  EyeOff,
  FastForward,
  Folder,
  Heart,
  HeartOff,
  House,
  Info,
  Lock,
  LockOpen,
  Mail,
  MapPin,
  Menu,
  MoreHorizontal,
  MoreVertical,
  Paperclip,
  Pause,
  Pencil,
  Phone,
  Play,
  Plus,
  Printer,
  RefreshCw,
  Rewind,
  Search,
  Send,
  Settings,
  Share2,
  ShoppingCart,
  SkipBack,
  SkipForward,
  Sparkles,
  Square,
  Star,
  StarHalf,
  StarOff,
  Trash2,
  TriangleAlert,
  Upload,
  User,
  Volume1,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { JsonObject } from '../api/types'

const ICONS: Record<string, LucideIcon> = {
  accountCircle: CircleUserRound,
  add: Plus,
  arrowBack: ArrowLeft,
  arrowForward: ArrowRight,
  attachFile: Paperclip,
  calendarToday: Calendar,
  call: Phone,
  camera: Camera,
  check: Check,
  close: X,
  delete: Trash2,
  download: Download,
  edit: Pencil,
  event: CalendarDays,
  error: CircleAlert,
  fastForward: FastForward,
  favorite: Heart,
  favoriteOff: HeartOff,
  folder: Folder,
  help: CircleHelp,
  home: House,
  info: Info,
  locationOn: MapPin,
  lock: Lock,
  lockOpen: LockOpen,
  mail: Mail,
  menu: Menu,
  moreVert: MoreVertical,
  moreHoriz: MoreHorizontal,
  notificationsOff: BellOff,
  notifications: Bell,
  pause: Pause,
  payment: CreditCard,
  person: User,
  phone: Phone,
  photo: Sparkles,
  play: Play,
  print: Printer,
  refresh: RefreshCw,
  rewind: Rewind,
  search: Search,
  send: Send,
  settings: Settings,
  share: Share2,
  shoppingCart: ShoppingCart,
  skipNext: SkipForward,
  skipPrevious: SkipBack,
  star: Star,
  starHalf: StarHalf,
  starOff: StarOff,
  stop: Square,
  upload: Upload,
  visibility: Eye,
  visibilityOff: EyeOff,
  volumeDown: Volume1,
  volumeMute: VolumeX,
  volumeOff: VolumeX,
  volumeUp: Volume2,
  warning: TriangleAlert,
}

interface A2UIIconProps {
  name: unknown
  size?: number
}

export function A2UIIcon({ name, size = 18 }: A2UIIconProps) {
  if (typeof name === 'string') {
    const Icon = ICONS[name] ?? Sparkles
    return <Icon size={size} aria-hidden="true" />
  }

  if (name && typeof name === 'object' && 'svgPath' in name) {
    const svgPath = (name as JsonObject).svgPath
    if (typeof svgPath === 'string') {
      return (
        <svg
          width={size}
          height={size}
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d={svgPath} />
        </svg>
      )
    }
  }

  return <Sparkles size={size} aria-hidden="true" />
}
