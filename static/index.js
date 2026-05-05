window.PageHexarena = {
  template: '#page-hexarena',
  data() {
    return {
      activeTab: 'games',
      gameFilter: '',
      runFilter: '',
      summaryLoading: false,
      gameOptions: [],
      runOptions: [],
      statusOptions: {
        game: ['draft', 'active', 'disabled'],
        run: ['waiting', 'running', 'finished', 'cancelled'],
        agent: ['pending_payment', 'active', 'alive', 'eliminated', 'paid']
      },
      payoutSchemeOptions: [
        {label: 'Winner takes all', value: 'winner_takes_all'},
        {label: 'Top 3 (60 / 30 / 10)', value: 'top_3_60_30_10'}
      ],
      gameFormDialog: {
        show: false,
        data: {}
      },
      runFormDialog: {
        show: false,
        data: {}
      },
      agentFormDialog: {
        show: false,
        data: {}
      },
      finishRunDialog: {
        show: false,
        data: {
          run_id: null,
          winner_agent_id: null
        }
      },
      payoutDialog: {
        show: false,
        data: {
          agent_id: null,
          payment_request: null
        }
      },
      games: [],
      runs: [],
      agents: [],
      joinRequests: [],
      autoRefreshTimer: null,
      gamesTable: {
        search: '',
        loading: false,
        filter: {},
        columns: [],
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 0
        }
      },
      runsTable: {
        search: '',
        loading: false,
        filter: {},
        columns: [],
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 0
        }
      },
      agentsTable: {
        search: '',
        loading: false,
        filter: {},
        columns: [],
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 0
        }
      },
      joinRequestsTable: {
        search: '',
        loading: false,
        filter: {},
        columns: [],
        pagination: {
          sortBy: 'updated_at',
          rowsPerPage: 10,
          page: 1,
          descending: true,
          rowsNumber: 0
        }
      }
    }
  },
  computed: {
    selectedGame() {
      return (
        this.gameOptions.find(game => game.value === this.gameFilter) || null
      )
    },
    filteredRunOptions() {
      if (!this.gameFilter) {
        return this.runOptions
      }
      return this.runOptions.filter(run => run.game_id === this.gameFilter)
    },
    currentRunChoices() {
      return this.filteredRunOptions.map(run => ({
        label: `${run.label} (${run.status})`,
        value: run.value
      }))
    },
    currentGameChoices() {
      return this.gameOptions.map(game => ({
        label: game.label,
        value: game.value
      }))
    },
    runSummary() {
      const summary = {
        waiting: 0,
        running: 0,
        finished: 0,
        cancelled: 0
      }
      this.runs.forEach(run => {
        if (summary[run.status] !== undefined) {
          summary[run.status] += 1
        }
      })
      return summary
    }
  },
  methods: {
    initializeTables() {
      this.gamesTable.columns = this.buildGamesColumns()
      this.runsTable.columns = this.buildRunsColumns()
      this.agentsTable.columns = this.buildAgentsColumns()
      this.joinRequestsTable.columns = this.buildJoinRequestsColumns()
    },
    buildGamesColumns() {
      return [
        {
          name: 'name',
          align: 'left',
          label: 'Game',
          field: 'name',
          sortable: true
        },
        {
          name: 'status',
          align: 'left',
          label: 'Status',
          field: 'status',
          sortable: true
        },
        {
          name: 'wallet_id',
          align: 'left',
          label: 'Wallet',
          field: 'wallet_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'fee_wallet_id',
          align: 'left',
          label: 'Fee Wallet',
          field: 'fee_wallet_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'latest_run_id',
          align: 'left',
          label: 'Latest Run',
          field: 'latest_run_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'updated_at',
          align: 'left',
          label: 'Updated',
          field: 'updated_at',
          sortable: true,
          format: value => this.dateFromNow(value)
        }
      ]
    },
    buildRunsColumns() {
      return [
        {
          name: 'id',
          align: 'left',
          label: 'Run ID',
          field: 'id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'game_id',
          align: 'left',
          label: 'Game ID',
          field: 'game_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'status',
          align: 'left',
          label: 'Status',
          field: 'status',
          sortable: true
        },
        {
          name: 'turn',
          align: 'right',
          label: 'Turn',
          field: 'turn',
          sortable: true
        },
        {
          name: 'prize_pool_sats',
          align: 'right',
          label: 'Prize Pool',
          field: 'prize_pool_sats',
          sortable: true,
          format: value => this.satLabel(value)
        },
        {
          name: 'fee_status',
          align: 'left',
          label: 'Fees',
          field: 'fee_status',
          sortable: true
        },
        {
          name: 'winner_agent_id',
          align: 'left',
          label: 'Winner',
          field: 'winner_agent_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'updated_at',
          align: 'left',
          label: 'Updated',
          field: 'updated_at',
          sortable: true,
          format: value => this.dateFromNow(value)
        }
      ]
    },
    buildAgentsColumns() {
      return [
        {
          name: 'display_name',
          align: 'left',
          label: 'Agent',
          field: 'display_name',
          sortable: true
        },
        {
          name: 'run_id',
          align: 'left',
          label: 'Run ID',
          field: 'run_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'status',
          align: 'left',
          label: 'Status',
          field: 'status',
          sortable: true
        },
        {
          name: 'start_hex_id',
          align: 'left',
          label: 'Start Hex',
          field: 'start_hex_id',
          sortable: true
        },
        {
          name: 'payout_amount_sats',
          align: 'right',
          label: 'Payout',
          field: 'payout_amount_sats',
          sortable: true,
          format: value => this.satLabel(value)
        },
        {
          name: 'payout_status',
          align: 'left',
          label: 'Payout Status',
          field: 'payout_status',
          sortable: true
        },
        {
          name: 'joined_at',
          align: 'left',
          label: 'Joined',
          field: 'joined_at',
          sortable: true,
          format: value => this.dateFromNow(value)
        },
        {
          name: 'updated_at',
          align: 'left',
          label: 'Updated',
          field: 'updated_at',
          sortable: true,
          format: value => this.dateFromNow(value)
        }
      ]
    },
    buildJoinRequestsColumns() {
      return [
        {
          name: 'display_name',
          align: 'left',
          label: 'Player',
          field: 'display_name',
          sortable: true
        },
        {
          name: 'run_id',
          align: 'left',
          label: 'Run ID',
          field: 'run_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'status',
          align: 'left',
          label: 'Status',
          field: 'status',
          sortable: true
        },
        {
          name: 'paid',
          align: 'left',
          label: 'Paid',
          field: 'paid',
          sortable: true,
          format: value => (value ? 'paid' : 'pending')
        },
        {
          name: 'agent_id',
          align: 'left',
          label: 'Agent ID',
          field: 'agent_id',
          sortable: true,
          format: value => this.shorten(value)
        },
        {
          name: 'expires_at',
          align: 'left',
          label: 'Expires',
          field: 'expires_at',
          sortable: true,
          format: value => this.dateFromNow(value)
        },
        {
          name: 'settled_at',
          align: 'left',
          label: 'Settled',
          field: 'settled_at',
          sortable: true,
          format: value => this.dateFromNow(value)
        },
        {
          name: 'updated_at',
          align: 'left',
          label: 'Updated',
          field: 'updated_at',
          sortable: true,
          format: value => this.dateFromNow(value)
        }
      ]
    },
    defaultConfig() {
      return {
        min_players: 2,
        max_players: 8,
        poll_interval_sec: 10,
        auto_start_after_sec: 60,
        max_rounds: 120,
        entry_fee_sats: 0,
        base_hex_count: 40,
        power_growth_every_n_turns: 10,
        powerup_spawn_every_n_turns: 12,
        starting_power_new_hex: 1,
        payout_scheme: 'winner_takes_all',
        enable_fortify: true,
        pot_rollover: false,
        house_fee_percent: 0,
        terrain_distribution: {},
        powerup_types_enabled: []
      }
    },
    emptyGameForm() {
      return {
        name: '',
        wallet_id: this.g.user.walletOptions?.[0]?.value || null,
        fee_wallet_id: null,
        status: 'draft',
        default_config: this.defaultConfig()
      }
    },
    emptyRunForm(gameId = null) {
      const game = this.gameOptions.find(option => option.value === gameId)?.raw
      return {
        id: null,
        game_id: gameId,
        status: 'waiting',
        config: this.mergeConfig(game?.default_config || {})
      }
    },
    emptyAgentForm() {
      return {
        id: null,
        display_name: '',
        status: 'active',
        payout_request: '',
        inventory_text: '',
        profile_text: '{}'
      }
    },
    mergeConfig(config = {}) {
      return {
        ...this.defaultConfig(),
        ...this.clone(config)
      }
    },
    clone(value) {
      return JSON.parse(JSON.stringify(value))
    },
    shorten(value) {
      if (!value) return '-'
      return value.length > 16
        ? `${value.slice(0, 8)}...${value.slice(-4)}`
        : value
    },
    satLabel(value) {
      return LNbits.utils.formatBalance(value || 0, 'sats')
    },
    formatDate(value) {
      return value ? LNbits.utils.formatDate(value) : '-'
    },
    dateFromNow(value) {
      return value ? LNbits.utils.formatDateFrom(value) : '-'
    },
    copyText(value, label = 'Value') {
      if (!value) return
      LNbits.utils.copyText(value, `${label} copied`)
    },
    openPublicRun(runId) {
      const href = runId
        ? `/hexarena/play?run=${encodeURIComponent(runId)}`
        : '/hexarena/play'
      window.open(href, '_blank')
    },
    startAutoRefresh() {
      this.stopAutoRefresh()
      this.autoRefreshTimer = setInterval(() => {
        this.reloadAll()
      }, 30000)
    },
    stopAutoRefresh() {
      if (this.autoRefreshTimer) {
        clearInterval(this.autoRefreshTimer)
        this.autoRefreshTimer = null
      }
    },
    statusColor(status) {
      const colors = {
        draft: 'grey-6',
        active: 'positive',
        disabled: 'negative',
        waiting: 'warning',
        running: 'primary',
        finished: 'positive',
        cancelled: 'negative',
        pending_payment: 'warning',
        alive: 'primary',
        eliminated: 'negative',
        paid: 'positive',
        none: 'grey-6',
        pending: 'warning',
        settled: 'positive',
        failed: 'negative',
        expired: 'negative'
      }
      return colors[status] || 'grey-6'
    },
    parseJsonText(value, fallback) {
      if (!value || !value.trim()) {
        return fallback
      }
      return JSON.parse(value)
    },
    async fetchGameOptions() {
      const {data} = await LNbits.api.request(
        'GET',
        '/hexarena/api/v1/games/paginated?limit=200&offset=0&sortby=updated_at&direction=desc',
        null
      )
      this.gameOptions = data.data.map(game => ({
        label: game.name,
        value: game.id,
        raw: game
      }))
    },
    async fetchRunOptions() {
      const {data} = await LNbits.api.request(
        'GET',
        '/hexarena/api/v1/runs/paginated?limit=200&offset=0&sortby=updated_at&direction=desc',
        null
      )
      this.runOptions = data.data.map(run => ({
        label: this.shorten(run.id),
        value: run.id,
        status: run.status,
        game_id: run.game_id,
        raw: run
      }))
    },
    async refreshOptions() {
      await this.fetchGameOptions()
      await this.fetchRunOptions()
    },
    showNewGameForm() {
      this.gameFormDialog.data = this.emptyGameForm()
      this.gameFormDialog.show = true
    },
    showEditGameForm(game) {
      this.gameFormDialog.data = {
        id: game.id,
        name: game.name,
        wallet_id: game.wallet_id,
        fee_wallet_id: game.fee_wallet_id,
        status: game.status,
        default_config: this.mergeConfig(game.default_config)
      }
      this.gameFormDialog.show = true
    },
    async saveGame() {
      try {
        const data = this.clone(this.gameFormDialog.data)
        const method = data.id ? 'PUT' : 'POST'
        const endpoint = data.id
          ? `/hexarena/api/v1/games/${data.id}`
          : '/hexarena/api/v1/games'
        delete data.id
        if (!data.fee_wallet_id) {
          data.fee_wallet_id = null
        }
        await LNbits.api.request(method, endpoint, null, data)
        this.gameFormDialog.show = false
        await Promise.all([
          this.getGames(),
          this.getRuns(),
          this.refreshOptions()
        ])
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async getGames(props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.gamesTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/hexarena/api/v1/games/paginated?${params}`,
          null
        )
        this.games = data.data
        this.gamesTable.pagination.rowsNumber = data.total
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.gamesTable.loading = false
      }
    },
    async deleteGame(gameId) {
      await LNbits.utils
        .confirmDialog('Delete this game and its reusable template?')
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              `/hexarena/api/v1/games/${gameId}`,
              null
            )
            await Promise.all([
              this.getGames(),
              this.getRuns(),
              this.refreshOptions()
            ])
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    exportGamesCsv() {
      LNbits.utils.exportCSV(
        this.gamesTable.columns,
        this.games,
        `hexarena_games_${new Date().toISOString().slice(0, 10)}`
      )
    },
    showNewRunForm(gameId = null) {
      this.runFormDialog.data = this.emptyRunForm(
        gameId || this.gameFilter || null
      )
      this.runFormDialog.show = true
    },
    showEditRunForm(run) {
      this.runFormDialog.data = {
        id: run.id,
        game_id: run.game_id,
        status: run.status,
        config: this.mergeConfig(run.config)
      }
      this.runFormDialog.show = true
    },
    onRunGameChanged(gameId) {
      if (!this.runFormDialog.data.id) {
        const game = this.gameOptions.find(
          option => option.value === gameId
        )?.raw
        this.runFormDialog.data.config = this.mergeConfig(
          game?.default_config || {}
        )
      }
    },
    async saveRun() {
      try {
        const data = this.clone(this.runFormDialog.data)
        const method = data.id ? 'PUT' : 'POST'
        const endpoint = data.id
          ? `/hexarena/api/v1/runs/${data.id}`
          : `/hexarena/api/v1/games/${data.game_id}/runs`
        const payload = {
          status: data.status,
          config: data.config
        }
        await LNbits.api.request(method, endpoint, null, payload)
        this.runFormDialog.show = false
        await Promise.all([
          this.getRuns(),
          this.getAgents(),
          this.getJoinRequests(),
          this.refreshOptions(),
          this.getGames()
        ])
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async getRuns(props) {
      try {
        let params = LNbits.utils.prepareFilterQuery(this.runsTable, props)
        if (this.gameFilter) {
          params += `&game_id=${encodeURIComponent(this.gameFilter)}`
        }
        const {data} = await LNbits.api.request(
          'GET',
          `/hexarena/api/v1/runs/paginated?${params}`,
          null
        )
        this.runs = data.data
        this.runsTable.pagination.rowsNumber = data.total
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.runsTable.loading = false
      }
    },
    async startRun(runId) {
      try {
        await LNbits.api.request(
          'POST',
          `/hexarena/api/v1/runs/${runId}/start`,
          null,
          {}
        )
        await Promise.all([
          this.getRuns(),
          this.getAgents(),
          this.refreshOptions()
        ])
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    openFinishRunDialog(run) {
      this.finishRunDialog.data = {
        run_id: run.id,
        winner_agent_id: run.winner_agent_id || null
      }
      this.finishRunDialog.show = true
    },
    async saveFinishRun() {
      try {
        await LNbits.api.request(
          'POST',
          `/hexarena/api/v1/runs/${this.finishRunDialog.data.run_id}/finish`,
          null,
          {winner_agent_id: this.finishRunDialog.data.winner_agent_id || null}
        )
        this.finishRunDialog.show = false
        await Promise.all([
          this.getRuns(),
          this.getAgents(),
          this.getJoinRequests()
        ])
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async cancelRun(runId) {
      await LNbits.utils
        .confirmDialog(
          'Cancel this run? This stops further actions and payouts stay based on current state.'
        )
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'POST',
              `/hexarena/api/v1/runs/${runId}/cancel`,
              null,
              {}
            )
            await Promise.all([
              this.getRuns(),
              this.getAgents(),
              this.getJoinRequests()
            ])
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    async retryRunFees(runId) {
      try {
        await LNbits.api.request(
          'POST',
          `/hexarena/api/v1/runs/${runId}/fees/retry`,
          null,
          {}
        )
        await this.getRuns()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async deleteRun(runId) {
      await LNbits.utils
        .confirmDialog('Delete this run and all related state?')
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              `/hexarena/api/v1/runs/${runId}`,
              null
            )
            await Promise.all([
              this.getRuns(),
              this.getAgents(),
              this.getJoinRequests(),
              this.refreshOptions(),
              this.getGames()
            ])
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    exportRunsCsv() {
      LNbits.utils.exportCSV(
        this.runsTable.columns,
        this.runs,
        `hexarena_runs_${new Date().toISOString().slice(0, 10)}`
      )
    },
    showEditAgentForm(agent) {
      this.agentFormDialog.data = {
        id: agent.id,
        display_name: agent.display_name || '',
        status: agent.status,
        payout_request: agent.payout_request || '',
        inventory_text: JSON.stringify(agent.inventory || []),
        profile_text: JSON.stringify(agent.profile || {}, null, 2)
      }
      this.agentFormDialog.show = true
    },
    async saveAgent() {
      try {
        const data = this.clone(this.agentFormDialog.data)
        const payload = {
          display_name: data.display_name || null,
          status: data.status,
          payout_request: data.payout_request || null,
          inventory: this.parseJsonText(data.inventory_text, []),
          profile: this.parseJsonText(data.profile_text, {})
        }
        await LNbits.api.request(
          'PUT',
          `/hexarena/api/v1/agents/${data.id}`,
          null,
          payload
        )
        this.agentFormDialog.show = false
        await this.getAgents()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async getAgents(props) {
      try {
        let params = LNbits.utils.prepareFilterQuery(this.agentsTable, props)
        if (this.runFilter) {
          params += `&run_id=${encodeURIComponent(this.runFilter)}`
        } else if (this.gameFilter) {
          params += `&game_id=${encodeURIComponent(this.gameFilter)}`
        }
        const {data} = await LNbits.api.request(
          'GET',
          `/hexarena/api/v1/agents/paginated?${params}`,
          null
        )
        this.agents = data.data
        this.agentsTable.pagination.rowsNumber = data.total
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.agentsTable.loading = false
      }
    },
    openPayoutDialog(agent) {
      this.payoutDialog.data = {
        agent_id: agent.id,
        payment_request: agent.payout_request || ''
      }
      this.payoutDialog.show = true
    },
    async settlePayout() {
      try {
        await LNbits.api.request(
          'POST',
          `/hexarena/api/v1/agents/${this.payoutDialog.data.agent_id}/settle-payout`,
          null,
          {payment_request: this.payoutDialog.data.payment_request}
        )
        this.payoutDialog.show = false
        await this.getAgents()
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    async deleteAgent(agentId) {
      await LNbits.utils
        .confirmDialog('Delete this agent record?')
        .onOk(async () => {
          try {
            await LNbits.api.request(
              'DELETE',
              `/hexarena/api/v1/agents/${agentId}`,
              null
            )
            await this.getAgents()
          } catch (error) {
            LNbits.utils.notifyApiError(error)
          }
        })
    },
    exportAgentsCsv() {
      LNbits.utils.exportCSV(
        this.agentsTable.columns,
        this.agents,
        `hexarena_agents_${new Date().toISOString().slice(0, 10)}`
      )
    },
    async getJoinRequests(props) {
      try {
        let params = LNbits.utils.prepareFilterQuery(
          this.joinRequestsTable,
          props
        )
        if (this.runFilter) {
          params += `&run_id=${encodeURIComponent(this.runFilter)}`
        } else if (this.gameFilter) {
          params += `&game_id=${encodeURIComponent(this.gameFilter)}`
        }
        const {data} = await LNbits.api.request(
          'GET',
          `/hexarena/api/v1/join-requests/paginated?${params}`,
          null
        )
        this.joinRequests = data.data
        this.joinRequestsTable.pagination.rowsNumber = data.total
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.joinRequestsTable.loading = false
      }
    },
    exportJoinRequestsCsv() {
      LNbits.utils.exportCSV(
        this.joinRequestsTable.columns,
        this.joinRequests,
        `hexarena_join_requests_${new Date().toISOString().slice(0, 10)}`
      )
    },
    async reloadAll() {
      this.summaryLoading = true
      try {
        await Promise.all([
          this.getGames(),
          this.getRuns(),
          this.getAgents(),
          this.getJoinRequests(),
          this.refreshOptions()
        ])
      } finally {
        this.summaryLoading = false
      }
    },
    onGameFilterChanged() {
      if (this.runFilter) {
        const runStillVisible = this.filteredRunOptions.some(
          run => run.value === this.runFilter
        )
        if (!runStillVisible) {
          this.runFilter = ''
        }
      }
      this.getRuns()
      this.getAgents()
      this.getJoinRequests()
    },
    onRunFilterChanged() {
      this.getAgents()
      this.getJoinRequests()
    }
  },
  async created() {
    this.initializeTables()
    await this.reloadAll()
    this.startAutoRefresh()
  },
  beforeDestroy() {
    this.stopAutoRefresh()
  }
}
