window.PageHexarenaPublic = {
  template: '#page-hexarena-public',
  data() {
    return {
      loading: false,
      runList: [],
      selectedRun: null,
      selectedGame: null,
      selectedRunState: null,
      hoveredTile: null,
      hoverPosition: {x: 0, y: 0},
      canvasHitRegions: [],
      runListPoller: null,
      selectedRunPoller: null,
      selectedRunSocket: null,
      resizeHandler: null,
      playerPalette: [
        '#ef4444',
        '#3b82f6',
        '#22c55e',
        '#f59e0b',
        '#a855f7',
        '#06b6d4',
        '#f97316',
        '#84cc16'
      ]
    }
  },
  computed: {
    runMetrics() {
      if (!this.runList.length) {
        return {
          openRuns: 0,
          lowestEntry: '-',
          fastestTurn: '-'
        }
      }
      return {
        openRuns: this.runList.length,
        lowestEntry: this.formatSats(
          Math.min(...this.runList.map(run => run.config.entry_fee_sats || 0))
        ),
        fastestTurn: `${Math.min(
          ...this.runList.map(run => run.config.poll_interval_sec || 0)
        )} sec`
      }
    },
    selectedRunHasMap() {
      return Boolean(this.selectedRunState && this.selectedRunState.hexes?.length)
    },
    selectedRunLeaderboard() {
      return this.selectedRunState?.leaderboard || []
    },
    selectedRunRecentActions() {
      const actions = this.selectedRunState?.recentActions || []
      return [...actions].sort((a, b) => {
        const aTime = a?.created_at ? new Date(a.created_at).getTime() : 0
        const bTime = b?.created_at ? new Date(b.created_at).getTime() : 0
        return bTime - aTime
      })
    },
    latestAction() {
      const actions = this.selectedRunRecentActions
      if (!actions.length) return null
      return actions.reduce((latest, action) => {
        if (!latest) return action
        const latestTime = latest.created_at ? new Date(latest.created_at).getTime() : 0
        const actionTime = action.created_at ? new Date(action.created_at).getTime() : 0
        return actionTime >= latestTime ? action : latest
      }, null)
    },
    selectedRunAgents() {
      return this.selectedRunState?.agents || []
    },
    playerColorMap() {
      const ids = []
      const leaderboardIds = (this.selectedRunState?.leaderboard || []).map(entry => entry.agentId)
      leaderboardIds.forEach(id => {
        if (id && !ids.includes(id)) ids.push(id)
      })
      this.selectedRunAgents.forEach(agent => {
        if (agent?.id && !ids.includes(agent.id)) ids.push(agent.id)
      })
      return ids.reduce((acc, agentId) => {
        acc[agentId] = this.hashColor(agentId)
        return acc
      }, {})
    },
    selectedRunMapSummary() {
      const hexes = this.selectedRunState?.hexes || []
      const owned = hexes.filter(tile => tile.owner).length
      const neutral = hexes.length - owned
      const contested = hexes.filter(tile => tile.adjacent?.some(adjacentId => {
        const adjacent = hexes.find(other => other.id === adjacentId)
        return adjacent?.owner && adjacent.owner !== tile.owner
      })).length
      return {
        total: hexes.length,
        owned,
        neutral,
        contested
      }
    },
    selectedRunTitle() {
      if (!this.selectedRun) return 'Arena'
      if (this.selectedGame?.name) return this.selectedGame.name
      return this.selectedRun.id
    },
    selectedRunSubtitle() {
      if (!this.selectedRun) return ''
      const mode = this.selectedRun.config.entry_fee_sats > 0 ? 'Paid match' : 'Open match'
      return `${mode} · ${this.selectedRun.config.base_hex_count} hexes · ${this.selectedRun.config.max_players} max players`
    },
    currentLeaderId() {
      return this.selectedRunLeaderboard[0]?.agentId || null
    }
  },
  methods: {
    async fetchRuns() {
      try {
        this.loading = true
        const {data} = await LNbits.api.request(
          'GET',
          '/hexarena/api/v1/public/runs',
          null
        )
        this.runList = data || []
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.loading = false
      }
    },
    async fetchRunDetail(runId, {background = false} = {}) {
      try {
        if (!background) {
          this.loading = true
        }
        const [{data: run}, {data: state}] = await Promise.all([
          LNbits.api.request('GET', `/hexarena/api/v1/public/runs/${runId}`, null),
          LNbits.api.request(
            'GET',
            `/hexarena/api/v1/public/runs/${runId}/state`,
            null
          )
        ])
        this.selectedRun = run
        this.selectedRunState = state

        if (!this.selectedGame || this.selectedGame.id !== run.game_id) {
          this.selectedGame = await this.fetchPublicGame(run.game_id)
        }

        this.$nextTick(() => {
          this.drawArena()
        })

        if (['finished', 'cancelled'].includes(run.status)) {
          this.stopSelectedRunRealtime()
        }
      } catch (error) {
        if (!background) {
          LNbits.utils.notifyApiError(error)
        }
      } finally {
        if (!background) {
          this.loading = false
        }
      }
    },
    async fetchPublicGame(gameId) {
      const response = await LNbits.api.request(
        'GET',
        `/hexarena/api/v1/public/games/${gameId}`,
        null
      )
      return response.data
    },
    setSelectedRunQuery(runId = null) {
      const url = new URL(window.location.href)
      if (runId) {
        url.searchParams.set('run', runId)
      } else {
        url.searchParams.delete('run')
      }
      window.history.replaceState({}, '', url.toString())
    },
    selectRun(run) {
      this.setSelectedRunQuery(run.id)
      this.fetchRunDetail(run.id)
      this.startSelectedRunRealtime(run.id)
    },
    backToIndex() {
      this.stopSelectedRunRealtime()
      this.setSelectedRunQuery(null)
      this.selectedRun = null
      this.selectedGame = null
      this.selectedRunState = null
    },
    startRunListPolling() {
      this.stopRunListPolling()
      this.runListPoller = setInterval(() => {
        if (!this.selectedRun) {
          this.fetchRuns()
        }
      }, 30000)
    },
    stopRunListPolling() {
      if (this.runListPoller) {
        clearInterval(this.runListPoller)
        this.runListPoller = null
      }
    },
    publicRunChannel(runId) {
      return `hexarena-public-run-${runId}`
    },
    startSelectedRunRealtime(runId) {
      this.stopSelectedRunRealtime()
      if (!runId) return
      this.initSelectedRunSocket(runId)
    },
    initSelectedRunSocket(runId) {
      try {
        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
        url.pathname = `/api/v1/ws/${this.publicRunChannel(runId)}`
        this.selectedRunSocket = new WebSocket(url)
        this.selectedRunSocket.onmessage = () => {
          this.fetchRunDetail(runId, {background: true})
        }
        this.selectedRunSocket.onerror = () => {
          this.startSelectedRunPolling(runId)
        }
        this.selectedRunSocket.onclose = () => {
          this.selectedRunSocket = null
          if (this.selectedRun?.id === runId && !this.selectedRunPoller) {
            this.startSelectedRunPolling(runId)
          }
        }
      } catch (error) {
        console.warn('HexArena public websocket failed to initialize', error)
        this.startSelectedRunPolling(runId)
      }
    },
    startSelectedRunPolling(runId) {
      this.stopSelectedRunPolling()
      if (!runId) return
      this.selectedRunPoller = setInterval(() => {
        this.fetchRunDetail(runId, {background: true})
      }, 30000)
    },
    stopSelectedRunPolling() {
      if (this.selectedRunPoller) {
        clearInterval(this.selectedRunPoller)
        this.selectedRunPoller = null
      }
    },
    stopSelectedRunRealtime() {
      this.stopSelectedRunPolling()
      if (this.selectedRunSocket) {
        this.selectedRunSocket.onclose = null
        this.selectedRunSocket.close()
        this.selectedRunSocket = null
      }
    },
    restoreSelectedRunFromQuery() {
      const url = new URL(window.location.href)
      const runId = url.searchParams.get('run')
      if (!runId) return
      this.fetchRunDetail(runId)
      this.startSelectedRunRealtime(runId)
    },
    formatSats(value) {
      return LNbits.utils.formatBalance(value || 0, 'sats')
    },
    formatDate(value) {
      return value ? LNbits.utils.formatDate(value) : '-'
    },
    formatDateFrom(value) {
      return value ? LNbits.utils.formatDateFrom(value) : '-'
    },
    statusColor(status) {
      const colors = {
        waiting: 'warning',
        running: 'positive',
        finished: 'grey-7',
        cancelled: 'negative',
        draft: 'blue-grey'
      }
      return colors[status] || 'grey'
    },
    ownerColor(ownerId) {
      if (!ownerId) {
        return '#9ca3af'
      }
      return this.playerColorMap[ownerId] || '#9ca3af'
    },
    displayNameForAgent(agentId) {
      if (!agentId) return 'Neutral'
      const leaderboardEntry = this.selectedRunLeaderboard.find(
        entry => entry.agentId === agentId
      )
      if (leaderboardEntry?.displayName) return leaderboardEntry.displayName
      const agentEntry = this.selectedRunAgents.find(entry => entry.id === agentId)
      if (agentEntry?.displayName) return agentEntry.displayName
      return this.shortId(agentId)
    },
    powerLabel(tile) {
      return `${tile.power || 0}`
    },
    actionSummary(action) {
      if (!action) return '-'
      const actor = action.agentId ? this.displayNameForAgent(action.agentId) : 'system'
      const target = action.targetHex ? ` -> ${action.targetHex}` : ''
      const message = action.message ? ` · ${action.message}` : ''
      return `${actor}: ${action.type}${target}${message}`
    },
    actionTypeColor(type) {
      const colors = {
        move: 'primary',
        attack: 'negative',
        fortify: 'warning',
        use_powerup: 'secondary'
      }
      return colors[type] || 'grey'
    },
    tileOwnerLabel(tile) {
      if (!tile?.owner) return 'Neutral'
      return this.displayNameForAgent(tile.owner)
    },
    agentStatus(agentId) {
      const agent = this.selectedRunAgents.find(entry => entry.id === agentId)
      if (!agent) return 'Unknown'
      return agent.eliminated ? 'Eliminated' : 'Active'
    },
    terrainGlyph(terrain) {
      const glyphs = {
        plains: '',
        forest: 'F',
        mountain: 'M',
        water: ''
      }
      return glyphs[terrain] || ''
    },
    terrainNeutralFill(terrain) {
      const fills = {
        plains: 'rgba(148, 163, 184, 0.12)',
        forest: 'rgba(34, 197, 94, 0.12)',
        mountain: 'rgba(148, 163, 184, 0.2)',
        water: 'rgba(15, 23, 42, 0.34)'
      }
      return fills[terrain] || fills.plains
    },
    terrainNeutralStroke(terrain) {
      const strokes = {
        plains: 'rgba(148, 163, 184, 0.38)',
        forest: 'rgba(34, 197, 94, 0.28)',
        mountain: 'rgba(148, 163, 184, 0.45)',
        water: 'rgba(15, 23, 42, 0.6)'
      }
      return strokes[terrain] || strokes.plains
    },
    shortId(value) {
      if (!value) return '-'
      return value.length <= 12 ? value : `${value.slice(0, 6)}...${value.slice(-4)}`
    },
    hashColor(value) {
      let hash = 0
      for (let index = 0; index < value.length; index += 1) {
        hash = (hash * 31 + value.charCodeAt(index)) % 360
      }
      return `hsl(${hash} 72% 58%)`
    },
    glowStroke(color, alpha = 0.38) {
      const hex = (color || '#ffffff').replace('#', '')
      if (hex.length !== 6) return `rgba(255, 255, 255, ${alpha})`
      const r = Number.parseInt(hex.slice(0, 2), 16)
      const g = Number.parseInt(hex.slice(2, 4), 16)
      const b = Number.parseInt(hex.slice(4, 6), 16)
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    },
    isPointInsidePolygon(pointX, pointY, polygon) {
      let inside = false
      for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].x
        const yi = polygon[i].y
        const xj = polygon[j].x
        const yj = polygon[j].y
        const intersects =
          yi > pointY !== yj > pointY &&
          pointX < ((xj - xi) * (pointY - yi)) / (yj - yi || 1e-9) + xi
        if (intersects) inside = !inside
      }
      return inside
    },
    handleCanvasMove(event) {
      const canvas = this.$refs.arenaCanvas
      if (!canvas || !this.canvasHitRegions.length) return
      const rect = canvas.getBoundingClientRect()
      const pointX = event.clientX - rect.left
      const pointY = event.clientY - rect.top
      const hit = this.canvasHitRegions.find(region =>
        this.isPointInsidePolygon(pointX, pointY, region.polygon)
      )
      this.hoveredTile = hit ? hit.tile : null
      this.hoverPosition = {
        x: pointX + 16,
        y: pointY + 16
      }
    },
    clearCanvasHover() {
      this.hoveredTile = null
    },
    drawArena() {
      if (!this.selectedRunState?.hexes?.length) {
        this.canvasHitRegions = []
        return
      }
      const canvas = this.$refs.arenaCanvas
      const container = this.$refs.arenaCanvasWrap
      if (!canvas || !container) {
        return
      }

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        return
      }

      const tiles = this.selectedRunState.hexes
      const width = Math.max(480, container.clientWidth || 480)
      const viewportHeight = Math.max(420, Math.floor(window.innerHeight * 0.9))
      const targetHeight = Math.round(width * 0.72)
      const height = Math.min(viewportHeight, Math.max(420, targetHeight))
      const dpr = window.devicePixelRatio || 1
      canvas.width = width * dpr
      canvas.height = height * dpr
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)
      const background = ctx.createLinearGradient(0, 0, width, height)
      background.addColorStop(0, 'rgba(15, 23, 42, 0.18)')
      background.addColorStop(1, 'rgba(59, 130, 246, 0.06)')
      ctx.fillStyle = background
      ctx.fillRect(0, 0, width, height)

      const xStep = Math.sqrt(3)
      const yStep = 1.5
      const points = tiles.map(tile => ({
        tile,
        x: xStep * (tile.q + tile.r / 2),
        y: yStep * tile.r
      }))
      const latestTargetHex = this.latestAction?.targetHex || null
      const leaderId = this.currentLeaderId

      const xs = points.map(point => point.x)
      const ys = points.map(point => point.y)
      const minX = Math.min(...xs)
      const maxX = Math.max(...xs)
      const minY = Math.min(...ys)
      const maxY = Math.max(...ys)
      const spanX = Math.max(1, maxX - minX)
      const spanY = Math.max(1, maxY - minY)
      const size = Math.max(
        12,
        Math.min((width - 48) / (spanX + 2.5), (height - 48) / (spanY + 2.5))
      )
      const offsetX = width / 2 - ((minX + maxX) / 2) * size
      const offsetY = height / 2 - ((minY + maxY) / 2) * size

      ctx.lineWidth = 1.25
      ctx.font = '600 12px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      this.canvasHitRegions = []

      points.forEach(point => {
        const centerX = point.x * size + offsetX
        const centerY = point.y * size + offsetY
        const fill = point.tile.owner
          ? this.ownerColor(point.tile.owner)
          : this.terrainNeutralFill(point.tile.terrain)
        const stroke = point.tile.owner
          ? this.ownerColor(point.tile.owner)
          : this.terrainNeutralStroke(point.tile.terrain)

        const polygon = []
        ctx.beginPath()
        for (let side = 0; side < 6; side += 1) {
          const angle = ((60 * side - 30) * Math.PI) / 180
          const px = centerX + size * Math.cos(angle)
          const py = centerY + size * Math.sin(angle)
          polygon.push({x: px, y: py})
          if (side === 0) {
            ctx.moveTo(px, py)
          } else {
            ctx.lineTo(px, py)
          }
        }
        ctx.closePath()
        ctx.fillStyle = fill
        ctx.strokeStyle = stroke
        ctx.fill()
        ctx.stroke()

        if (point.tile.owner && point.tile.owner === leaderId) {
          ctx.save()
          ctx.lineWidth = 2.5
          ctx.strokeStyle = this.glowStroke(this.ownerColor(point.tile.owner), 0.55)
          ctx.stroke()
          ctx.restore()
        }

        if (latestTargetHex && point.tile.id === latestTargetHex) {
          ctx.save()
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.92)'
          ctx.lineWidth = 3
          ctx.setLineDash([5, 4])
          ctx.stroke()
          ctx.setLineDash([])
          ctx.beginPath()
          ctx.arc(centerX, centerY, Math.max(15, size * 0.72), 0, Math.PI * 2)
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.42)'
          ctx.lineWidth = 2
          ctx.stroke()
          ctx.restore()
        }

        if (point.tile.owner) {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.16)'
          ctx.beginPath()
          ctx.arc(centerX, centerY, Math.max(9, size * 0.42), 0, Math.PI * 2)
          ctx.fill()
        }

        const terrainGlyph = this.terrainGlyph(point.tile.terrain)
        if (terrainGlyph && size > 16) {
          ctx.fillStyle = point.tile.owner ? 'rgba(17, 24, 39, 0.7)' : 'rgba(229, 231, 235, 0.7)'
          ctx.font = '600 10px sans-serif'
          ctx.fillText(terrainGlyph, centerX, centerY - Math.max(8, size * 0.34))
        }

        ctx.fillStyle = point.tile.owner ? '#111827' : '#e5e7eb'
        ctx.font = '700 14px sans-serif'
        ctx.fillText(this.powerLabel(point.tile), centerX, centerY)

        this.canvasHitRegions.push({
          tile: point.tile,
          polygon
        })
      })
    }
  },
  async created() {
    await this.fetchRuns()
    this.startRunListPolling()
    this.restoreSelectedRunFromQuery()
  },
  mounted() {
    this.resizeHandler = () => {
      this.drawArena()
    }
    window.addEventListener('resize', this.resizeHandler)
  },
  beforeUnmount() {
    this.stopRunListPolling()
    this.stopSelectedRunRealtime()
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler)
      this.resizeHandler = null
    }
  }
}
