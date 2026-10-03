import type { SVGProps } from 'react'
import { siDocker, siFastapi, siGithubactions, siOllama, siPrometheus, siReact, siSqlite } from 'simple-icons'
import {
  Activity,
  Box,
  Braces,
  ClipboardCheck,
  Cloud,
  Cpu,
  Eye,
  EyeOff,
  FileText,
  Fingerprint,
  Gauge,
  GitBranch,
  Hash,
  HardDrive,
  Key,
  ListChecks,
  ListOrdered,
  MailX,
  MessageSquare,
  Plug,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  ZapOff,
  type LucideIcon,
} from 'lucide-react'

interface SimpleIconData {
  path: string
  title: string
}

/** simple-icons has no React components - these are raw SVG path data, rendered below via `fill="currentColor"` so brand marks follow the poster's text color instead of their own brand hex. */
const BRAND_ICONS: Record<string, SimpleIconData> = {
  docker: siDocker,
  githubactions: siGithubactions,
  fastapi: siFastapi,
  sqlite: siSqlite,
  ollama: siOllama,
  react: siReact,
  prometheus: siPrometheus,
}

/** `groq` has no simple-icons brand mark (as of this package version) - Cpu stands in for an inference chip. */
const LUCIDE_ICONS: Record<string, LucideIcon> = {
  hash: Hash,
  hardDrive: HardDrive,
  gitBranch: GitBranch,
  listOrdered: ListOrdered,
  zapOff: ZapOff,
  refreshCw: RefreshCw,
  shieldCheck: ShieldCheck,
  braces: Braces,
  eye: Eye,
  plug: Plug,
  cloud: Cloud,
  fingerprint: Fingerprint,
  mailX: MailX,
  key: Key,
  gauge: Gauge,
  shieldAlert: ShieldAlert,
  eyeOff: EyeOff,
  listChecks: ListChecks,
  messageSquare: MessageSquare,
  activity: Activity,
  fileText: FileText,
  clipboardCheck: ClipboardCheck,
  groq: Cpu,
}

interface ArchIconProps extends SVGProps<SVGSVGElement> {
  icon: string
  size?: number
}

/** Renders a backend `icon` slug as either a simple-icons brand mark or a lucide-react icon, falling back to a generic box so an unmapped slug degrades instead of crashing. */
export function ArchIcon({ icon, size = 18, ...props }: ArchIconProps) {
  const brand = BRAND_ICONS[icon]
  if (brand) {
    return (
      <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" role="img" {...props}>
        <title>{brand.title}</title>
        <path d={brand.path} />
      </svg>
    )
  }
  const Lucide = LUCIDE_ICONS[icon] ?? Box
  return <Lucide width={size} height={size} aria-hidden="true" {...props} />
}
