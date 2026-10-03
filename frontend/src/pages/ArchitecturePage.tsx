import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Background, Controls, Panel, ReactFlow, useReactFlow } from '@xyflow/react'
import type { Edge, Node } from '@xyflow/react'
import { toPng, toSvg } from 'html-to-image'
import '@xyflow/react/dist/style.css'
import { archApi, healthApi, tracesApi } from '../lib/api'
import type {
  ArchGraphResponse,
  ArchLiveRunEvent,
  ArchLiveRunRequest,
  ArchNode,
  ArchScenarioStep,
  ArchStatusResponse,
  ArchTestRunResponse,
} from '../lib/types'
import { layoutGraph, type ArchEdgeRenderData, type ArchNodeRenderData } from '../lib/archLayout'
import { filterGraphForExtras } from '../lib/archExtras'
import { graphToMermaid } from '../lib/mermaid'
import { ArchGroupNode } from '../components/arch/ArchGroupNode'
import { ArchNodeCard } from '../components/arch/ArchNodeCard'
import { ArchEdgeLine } from '../components/arch/ArchEdgeLine'
import { NodeDetailDrawer } from '../components/arch/NodeDetailDrawer'
import { EdgeDetailPopover } from '../components/arch/EdgeDetailPopover'
import { ScenarioRunner } from '../components/arch/ScenarioRunner'
import { LiveRunPanel } from '../components/arch/LiveRunPanel'
import { Legend } from '../components/arch/Legend'
import { StatusBar } from '../components/arch/StatusBar'
import { DOCK_DEFAULT_WIDTH, SideDock } from '../components/arch/SideDock'
import { INSPECTOR_DEFAULT_HEIGHT, InspectorDock } from '../components/arch/InspectorDock'
import { Toast, type ToastData } from '../components/ui/Toast'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'

const NODE_TYPES = { archGroup: ArchGroupNode, archNode: ArchNodeCard }
const EDGE_TYPES = { archEdge: ArchEdgeLine }
const STATUS_POLL_MS = 5000
const LIVE_TRAFFIC_POLL_MS = 3000
const PULSE_DURATION_MS = 1200
const SHOW_EXTRAS_STORAGE_KEY = 'arch:showExtras'
const PANEL_MODE_STORAGE_KEY = 'arch:panelMode'
const DOCK_WIDTH_STORAGE_KEY = 'arch:dockWidth'
const DOCK_COLLAPSED_STORAGE_KEY = 'arch:dockCollapsed'
const INSPECTOR_HEIGHT_STORAGE_KEY = 'arch:inspectorHeight'
const INSPECTOR_COLLAPSED_STORAGE_KEY = 'arch:inspectorCollapsed'

function loadShowExtras(): boolean {
  try {
    return localStorage.getItem(SHOW_EXTRAS_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

type PanelMode = 'scenarios' | 'liveRun'

function loadPanelMode(): PanelMode {
  try {
    return localStorage.getItem(PANEL_MODE_STORAGE_KEY) === 'liveRun' ? 'liveRun' : 'scenarios'
  } catch {
    return 'scenarios'
  }
}

function loadDockWidth(): number {
  try {
    const stored = Number(localStorage.getItem(DOCK_WIDTH_STORAGE_KEY))
    return Number.isFinite(stored) && stored > 0 ? stored : DOCK_DEFAULT_WIDTH
  } catch {
    return DOCK_DEFAULT_WIDTH
  }
}

function loadDockCollapsed(): boolean {
  try {
    const stored = localStorage.getItem(DOCK_COLLAPSED_STORAGE_KEY)
    return stored === null ? true : stored === 'true'
  } catch {
    return true
  }
}

function loadInspectorHeight(): number {
  try {
    const stored = Number(localStorage.getItem(INSPECTOR_HEIGHT_STORAGE_KEY))
    return Number.isFinite(stored) && stored > 0 ? stored : INSPECTOR_DEFAULT_HEIGHT
  } catch {
    return INSPECTOR_DEFAULT_HEIGHT
  }
}

function loadInspectorCollapsed(): boolean {
  try {
    const stored = localStorage.getItem(INSPECTOR_COLLAPSED_STORAGE_KEY)
    return stored === null ? true : stored === 'true'
  } catch {
    return true
  }
}

function FitViewButton() {
  const { fitView } = useReactFlow()
  return (
    <Button variant="secondary" onClick={() => void fitView({ duration: 300 })} className="px-3 py-1.5 text-xs">
      Fit view
    </Button>
  )
}

function ResetButton({ onReset }: { onReset: () => void }) {
  const { fitView } = useReactFlow()
  return (
    <Button
      variant="secondary"
      className="px-3 py-1.5 text-xs"
      onClick={() => {
        onReset()
        void fitView({ duration: 300 })
      }}
    >
      Reset
    </Button>
  )
}

/** Re-fits the view whenever `version` changes - bumped after each async layout resolves. */
function FitViewOnLayout({ version }: { version: number }) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    if (version === 0) return
    const raf = requestAnimationFrame(() => void fitView({ duration: 300 }))
    return () => cancelAnimationFrame(raf)
  }, [version, fitView])
  return null
}

function FitViewOnResize() {
  const { fitView } = useReactFlow()
  useEffect(() => {
    let timer: number | undefined
    function handleResize() {
      if (timer) window.clearTimeout(timer)
      timer = window.setTimeout(() => void fitView({ duration: 300 }), 150)
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      if (timer) window.clearTimeout(timer)
    }
  }, [fitView])
  return null
}

/** Re-fits after either dock collapses/expands or is resized - debounced so a resize drag doesn't thrash fitView on every pointermove. */
function FitViewOnDockChange({
  collapsed,
  width,
  inspectorCollapsed,
  inspectorHeight,
}: {
  collapsed: boolean
  width: number
  inspectorCollapsed: boolean
  inspectorHeight: number
}) {
  const { fitView } = useReactFlow()
  useEffect(() => {
    const timer = window.setTimeout(() => void fitView({ duration: 300 }), 150)
    return () => window.clearTimeout(timer)
  }, [collapsed, width, inspectorCollapsed, inspectorHeight, fitView])
  return null
}

export function ArchitecturePage() {
  const [graph, setGraph] = useState<ArchGraphResponse | null>(null)
  const [graphError, setGraphError] = useState<string | null>(null)
  const [status, setStatus] = useState<ArchStatusResponse | null>(null)
  const [statusLoading, setStatusLoading] = useState(false)
  const [buildTime, setBuildTime] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)
  const [showLegend, setShowLegend] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showExtras, setShowExtras] = useState(loadShowExtras)
  const [panelMode, setPanelMode] = useState<PanelMode>(loadPanelMode)
  const [dockCollapsed, setDockCollapsed] = useState(loadDockCollapsed)
  const [dockWidth, setDockWidth] = useState(loadDockWidth)
  const [inspectorCollapsed, setInspectorCollapsed] = useState(loadInspectorCollapsed)
  const [inspectorHeight, setInspectorHeight] = useState(loadInspectorHeight)
  const [liveRunEvents, setLiveRunEvents] = useState<ArchLiveRunEvent[]>([])
  const [liveRunRequestBody, setLiveRunRequestBody] = useState<ArchLiveRunRequest | null>(null)

  const [nodeRunStatus, setNodeRunStatus] = useState<Record<string, 'ok' | 'error' | 'modified'>>({})
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null)
  const [activeEdgeId, setActiveEdgeId] = useState<string | null>(null)
  const [shakeNodeId, setShakeNodeId] = useState<string | null>(null)
  const [edgeRunToken, setEdgeRunToken] = useState<Record<string, number>>({})
  const [toast, setToast] = useState<ToastData | null>(null)

  const [liveTrafficOn, setLiveTrafficOn] = useState(false)
  const [pulseNodeIds, setPulseNodeIds] = useState<Set<string>>(new Set())

  const toastIdRef = useRef(0)
  const shakeTimerRef = useRef<number | null>(null)
  const pulseTimersRef = useRef<Map<string, number>>(new Map())
  const flowWrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    archApi.graph().then(setGraph).catch(() => setGraphError('Could not load the architecture graph.'))
  }, [])

  useEffect(() => {
    healthApi
      .get()
      .then((health) => setBuildTime(health.build_time))
      .catch(() => setBuildTime(null))
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(SHOW_EXTRAS_STORAGE_KEY, String(showExtras))
    } catch {
      // best-effort persistence only
    }
  }, [showExtras])

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_MODE_STORAGE_KEY, panelMode)
    } catch {
      // best-effort persistence only
    }
  }, [panelMode])

  useEffect(() => {
    try {
      localStorage.setItem(DOCK_WIDTH_STORAGE_KEY, String(dockWidth))
    } catch {
      // best-effort persistence only
    }
  }, [dockWidth])

  useEffect(() => {
    try {
      localStorage.setItem(DOCK_COLLAPSED_STORAGE_KEY, String(dockCollapsed))
    } catch {
      // best-effort persistence only
    }
  }, [dockCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(INSPECTOR_HEIGHT_STORAGE_KEY, String(inspectorHeight))
    } catch {
      // best-effort persistence only
    }
  }, [inspectorHeight])

  useEffect(() => {
    try {
      localStorage.setItem(INSPECTOR_COLLAPSED_STORAGE_KEY, String(inspectorCollapsed))
    } catch {
      // best-effort persistence only
    }
  }, [inspectorCollapsed])

  useEffect(() => {
    void refreshStatus()
    const interval = setInterval(() => void refreshStatus(), STATUS_POLL_MS)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    return () => {
      if (shakeTimerRef.current) window.clearTimeout(shakeTimerRef.current)
      for (const timer of pulseTimersRef.current.values()) window.clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (!liveTrafficOn || !graph) return
    const graphSnapshot = graph
    const seen = new Set<string>()
    let primed = false
    let cancelled = false

    async function poll() {
      try {
        const spans = await tracesApi.list(50)
        if (cancelled) return
        if (!primed) {
          for (const span of spans) seen.add(span.span_id)
          primed = true
          return
        }
        for (const span of spans) {
          if (seen.has(span.span_id)) continue
          seen.add(span.span_id)
          for (const node of graphSnapshot.nodes) {
            if (node.trace_spans.includes(span.name)) pulseNode(node.id)
          }
        }
      } catch {
        // transient network hiccup - next poll retries
      }
    }

    void poll()
    const interval = setInterval(() => void poll(), LIVE_TRAFFIC_POLL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [liveTrafficOn, graph])

  function pulseNode(nodeId: string) {
    setPulseNodeIds((prev) => new Set(prev).add(nodeId))
    const existing = pulseTimersRef.current.get(nodeId)
    if (existing) window.clearTimeout(existing)
    const timer = window.setTimeout(() => {
      setPulseNodeIds((prev) => {
        const next = new Set(prev)
        next.delete(nodeId)
        return next
      })
      pulseTimersRef.current.delete(nodeId)
    }, PULSE_DURATION_MS)
    pulseTimersRef.current.set(nodeId, timer)
  }

  async function refreshStatus() {
    setStatusLoading(true)
    try {
      setStatus(await archApi.status())
    } catch {
      // status bar simply shows "checking..." indefinitely - non-fatal
    } finally {
      setStatusLoading(false)
    }
  }

  function showToast(data: Omit<ToastData, 'id'>) {
    toastIdRef.current += 1
    setToast({ ...data, id: toastIdRef.current })
  }

  function resetRunVisuals() {
    setNodeRunStatus({})
    setActiveNodeId(null)
    setActiveEdgeId(null)
    setShakeNodeId(null)
    setToast(null)
  }

  function handleScenarioStart() {
    resetRunVisuals()
    setDockCollapsed(false)
  }

  function handleScenarioStep(step: ArchScenarioStep) {
    setActiveNodeId(step.node_id)
    if (step.status === 'ok' || step.status === 'error') {
      setNodeRunStatus((prev) => ({ ...prev, [step.node_id]: step.status as 'ok' | 'error' }))
    }

    if (step.status === 'error') {
      setShakeNodeId(step.node_id)
      if (shakeTimerRef.current) window.clearTimeout(shakeTimerRef.current)
      shakeTimerRef.current = window.setTimeout(() => setShakeNodeId(null), 450)
      showToast({
        tone: 'danger',
        title: step.http_status ? `${step.http_status} ${step.error_code ?? ''}`.trim() : 'Scenario failed',
        detail: step.detail,
      })
    }

    if (step.edge_id) {
      const edgeId = step.edge_id
      setActiveEdgeId(edgeId)
      setEdgeRunToken((prev) => ({ ...prev, [edgeId]: (prev[edgeId] ?? 0) + 1 }))
    } else {
      setActiveEdgeId(null)
    }
  }

  function handleScenarioDone(result: ArchTestRunResponse) {
    setActiveNodeId(null)
    setActiveEdgeId(null)
    if (result.passed) {
      showToast({ tone: 'success', title: 'Scenario passed', detail: result.summary })
    }
    void refreshStatus()
  }

  function handleLiveRunStart(body: ArchLiveRunRequest) {
    resetRunVisuals()
    setDockCollapsed(false)
    setInspectorCollapsed(false)
    setLiveRunEvents([])
    setLiveRunRequestBody(body)
  }

  function handleLiveRunEvent(event: ArchLiveRunEvent) {
    setLiveRunEvents((prev) => [...prev, event])
    setActiveNodeId(event.node_id)
    if (event.status === 'passed' || event.status === 'failed' || event.status === 'modified') {
      setNodeRunStatus((prev) => ({
        ...prev,
        [event.node_id]: event.status === 'failed' ? 'error' : event.status === 'modified' ? 'modified' : 'ok',
      }))
    }

    if (event.status === 'failed') {
      setShakeNodeId(event.node_id)
      if (shakeTimerRef.current) window.clearTimeout(shakeTimerRef.current)
      shakeTimerRef.current = window.setTimeout(() => setShakeNodeId(null), 450)
      showToast({
        tone: 'danger',
        title: event.http_status ? `${event.http_status} ${event.error_code ?? ''}`.trim() : 'Live run failed',
        detail: event.output_summary ?? undefined,
      })
    }

    if (event.edge_ids.length > 0) {
      setEdgeRunToken((prev) => {
        const next = { ...prev }
        for (const edgeId of event.edge_ids) {
          next[edgeId] = (next[edgeId] ?? 0) + 1
        }
        return next
      })
      setActiveEdgeId(event.edge_ids[event.edge_ids.length - 1])
    } else {
      setActiveEdgeId(null)
    }
  }

  function handleLiveRunDone(passed: boolean, finalEvent: ArchLiveRunEvent | null) {
    setActiveNodeId(null)
    setActiveEdgeId(null)
    if (passed) {
      showToast({ tone: 'success', title: 'Live run passed', detail: finalEvent?.output_summary ?? undefined })
    }
    void refreshStatus()
  }

  function handleNodeActivate(id: string) {
    setSelectedNodeId(id)
    setDockCollapsed(false)
    setInspectorCollapsed(false)
  }

  function handleReset() {
    setNodeRunStatus({})
    setActiveNodeId(null)
    setActiveEdgeId(null)
    setShakeNodeId(null)
    setToast(null)
    setSelectedNodeId(null)
    setSelectedEdgeId(null)
    setPulseNodeIds(new Set())
  }

  async function handleExport(format: 'png' | 'svg') {
    if (!flowWrapperRef.current) return
    try {
      const dataUrl =
        format === 'png'
          ? await toPng(flowWrapperRef.current, { backgroundColor: '#050b18', pixelRatio: 2 })
          : await toSvg(flowWrapperRef.current, { backgroundColor: '#050b18' })
      const link = document.createElement('a')
      link.download = `structai-architecture.${format}`
      link.href = dataUrl
      link.click()
    } catch {
      showToast({ tone: 'danger', title: 'Export failed', detail: 'Could not render the diagram image.' })
    }
  }

  const visibleGraph = useMemo(
    () => (graph ? filterGraphForExtras(graph, showExtras) : null),
    [graph, showExtras],
  )

  useEffect(() => {
    if (!visibleGraph) return
    if (selectedNodeId && !visibleGraph.nodes.some((n) => n.id === selectedNodeId)) {
      setSelectedNodeId(null)
    }
    if (selectedEdgeId && !visibleGraph.edges.some((e) => e.id === selectedEdgeId)) {
      setSelectedEdgeId(null)
    }
  }, [visibleGraph, selectedNodeId, selectedEdgeId])

  const [baseLayout, setBaseLayout] = useState<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] })
  const [layoutVersion, setLayoutVersion] = useState(0)

  useEffect(() => {
    if (!visibleGraph) {
      setBaseLayout({ nodes: [], edges: [] })
      return
    }
    let cancelled = false
    void layoutGraph(visibleGraph).then((result) => {
      if (cancelled) return
      setBaseLayout(result)
      setLayoutVersion((v) => v + 1)
    })
    return () => {
      cancelled = true
    }
  }, [visibleGraph])

  const { nodes: baseNodes, edges: baseEdges } = baseLayout

  const nodes = useMemo<Node[]>(
    () =>
      baseNodes.map((n) => {
        if (n.type !== 'archNode') return n
        const data = n.data as ArchNodeRenderData
        return {
          ...n,
          selected: n.id === selectedNodeId,
          data: {
            ...data,
            active: n.id === activeNodeId || pulseNodeIds.has(n.id),
            runStatus: nodeRunStatus[n.id] ?? 'idle',
            shake: n.id === shakeNodeId,
            liveState: status?.nodes[n.id]?.state ?? null,
            statusDetail: status?.nodes[n.id] ?? null,
            onActivate: handleNodeActivate,
          } satisfies ArchNodeRenderData,
        }
      }),
    [baseNodes, selectedNodeId, activeNodeId, pulseNodeIds, nodeRunStatus, shakeNodeId, status],
  )

  const edges = useMemo<Edge[]>(
    () =>
      baseEdges.map((e) => {
        const data = e.data as ArchEdgeRenderData
        return {
          ...e,
          data: {
            ...data,
            active: e.id === activeEdgeId,
            runToken: edgeRunToken[e.id] ?? 0,
            onActivate: setSelectedEdgeId,
          } satisfies ArchEdgeRenderData,
        }
      }),
    [baseEdges, activeEdgeId, edgeRunToken],
  )

  const selectedNode: ArchNode | null = visibleGraph?.nodes.find((n) => n.id === selectedNodeId) ?? null
  const selectedEdge = visibleGraph?.edges.find((e) => e.id === selectedEdgeId) ?? null

  async function handleCopyMermaid() {
    if (!visibleGraph) return
    await navigator.clipboard.writeText(graphToMermaid(visibleGraph))
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (graphError) {
    return <p className="text-sm text-danger">{graphError}</p>
  }

  if (!graph || !visibleGraph) {
    return (
      <div className="flex items-center gap-2 text-sm text-text-dim">
        <Spinner /> Loading architecture graph...
      </div>
    )
  }

  return (
    <div className="-m-8 flex h-[calc(100vh-4rem)] flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3">
        <div>
          <h1 className="text-lg font-semibold text-text">Architecture</h1>
          <p className="text-xs text-text-dim">
            {visibleGraph.nodes.length} components across {visibleGraph.groups.length} layers -
            click a node or edge for details, or run a scenario to watch the request flow.
          </p>
        </div>
        <Button variant="secondary" onClick={() => void handleCopyMermaid()}>
          {copied ? 'Copied!' : 'Copy Mermaid'}
        </Button>
      </div>

      <StatusBar
        status={status}
        loading={statusLoading}
        onRefresh={() => void refreshStatus()}
        buildTime={buildTime}
      />

      <div className="flex flex-1 flex-col overflow-hidden md:flex-row">
        <div ref={flowWrapperRef} className="relative h-[55vh] flex-1 md:h-auto" style={{ background: '#050b18' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            nodesDraggable={false}
            nodesConnectable={false}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#1a2233" style={{ background: '#050b18' }} />
            <Controls showInteractive={false} />
            <FitViewOnLayout version={layoutVersion} />
            <FitViewOnResize />
            <FitViewOnDockChange
              collapsed={dockCollapsed}
              width={dockWidth}
              inspectorCollapsed={inspectorCollapsed}
              inspectorHeight={inspectorHeight}
            />
            <Panel position="top-left">
              <div className="flex flex-wrap gap-2">
                <FitViewButton />
                <ResetButton onReset={handleReset} />
                <Button
                  variant={showLegend ? 'primary' : 'secondary'}
                  className="px-3 py-1.5 text-xs"
                  onClick={() => setShowLegend((v) => !v)}
                >
                  Legend
                </Button>
                <Button
                  variant={liveTrafficOn ? 'primary' : 'secondary'}
                  className="px-3 py-1.5 text-xs"
                  onClick={() => setLiveTrafficOn((v) => !v)}
                >
                  Live traffic {liveTrafficOn ? 'on' : 'off'}
                </Button>
                <Button
                  variant={showExtras ? 'primary' : 'secondary'}
                  className="px-3 py-1.5 text-xs"
                  onClick={() => setShowExtras((v) => !v)}
                >
                  Show extras {showExtras ? 'on' : 'off'}
                </Button>
                <Button variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => void handleExport('png')}>
                  Export PNG
                </Button>
                <Button variant="secondary" className="px-3 py-1.5 text-xs" onClick={() => void handleExport('svg')}>
                  Export SVG
                </Button>
              </div>
            </Panel>
          </ReactFlow>
          <AnimatePresence>
            {showLegend && <Legend onClose={() => setShowLegend(false)} />}
          </AnimatePresence>
          <EdgeDetailPopover edge={selectedEdge ?? null} onClose={() => setSelectedEdgeId(null)} />
        </div>

        <SideDock
          collapsed={dockCollapsed}
          onCollapsedChange={setDockCollapsed}
          width={dockWidth}
          onWidthChange={setDockWidth}
          title={panelMode === 'scenarios' ? 'Test scenarios' : 'Live run'}
          headerExtra={
            <div className="flex gap-1 rounded-lg border border-border bg-bg p-0.5">
              <Button
                variant={panelMode === 'scenarios' ? 'primary' : 'ghost'}
                className="px-2 py-1 text-xs"
                onClick={() => setPanelMode('scenarios')}
              >
                Scenarios
              </Button>
              <Button
                variant={panelMode === 'liveRun' ? 'primary' : 'ghost'}
                className="px-2 py-1 text-xs"
                onClick={() => setPanelMode('liveRun')}
              >
                Live Run
              </Button>
            </div>
          }
        >
          {panelMode === 'scenarios' ? (
            <ScenarioRunner
              scenarios={visibleGraph.scenarios}
              onStart={handleScenarioStart}
              onStep={handleScenarioStep}
              onDone={handleScenarioDone}
            />
          ) : (
            <LiveRunPanel
              status={status}
              onStart={handleLiveRunStart}
              onEvent={handleLiveRunEvent}
              onDone={handleLiveRunDone}
            />
          )}
        </SideDock>
      </div>

      <InspectorDock
        collapsed={inspectorCollapsed}
        onCollapsedChange={setInspectorCollapsed}
        height={inspectorHeight}
        onHeightChange={setInspectorHeight}
        graph={visibleGraph}
        events={liveRunEvents}
        requestBody={liveRunRequestBody}
        onActivateNode={handleNodeActivate}
      />

      <NodeDetailDrawer
        node={selectedNode}
        graph={visibleGraph}
        status={status}
        onClose={() => setSelectedNodeId(null)}
        onNavigate={setSelectedNodeId}
      />
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  )
}
