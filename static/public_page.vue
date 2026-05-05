<template id="page-hexarena-public">
  <q-page class="hexarena-public q-pa-md">
    <div class="row justify-center">
      <div class="col-12 col-xl-10">
        <q-card bordered class="q-mb-lg">
          <q-card-section class="row items-start q-col-gutter-lg">
            <div class="col-12 col-lg-8">
              <div class="text-overline text-primary">HexArena Spectator</div>
              <div class="text-h3 text-weight-bold">Watch the board tilt in real time.</div>
              <div class="text-subtitle1 q-mt-sm">
                Open runs are listed below. Pick one and the public page turns into a live arena view with the map, standings, and recent actions.
              </div>
            </div>
            <div class="col-12 col-lg-4">
              <div class="row q-col-gutter-sm">
                <div class="col-12 col-sm-4 col-lg-12">
                  <q-card bordered>
                    <q-card-section>
                      <div class="text-overline">Open Runs</div>
                      <div class="text-h6" v-text="runMetrics.openRuns"></div>
                    </q-card-section>
                  </q-card>
                </div>
                <div class="col-12 col-sm-4 col-lg-12">
                  <q-card bordered>
                    <q-card-section>
                      <div class="text-overline">Lowest Entry</div>
                      <div class="text-h6" v-text="runMetrics.lowestEntry"></div>
                    </q-card-section>
                  </q-card>
                </div>
                <div class="col-12 col-sm-4 col-lg-12">
                  <q-card bordered>
                    <q-card-section>
                      <div class="text-overline">Fastest Turn</div>
                      <div class="text-h6" v-text="runMetrics.fastestTurn"></div>
                    </q-card-section>
                  </q-card>
                </div>
              </div>
            </div>
          </q-card-section>
        </q-card>

        <div v-if="loading" class="row justify-center q-py-xl">
          <q-spinner-bars color="primary" size="4em"></q-spinner-bars>
        </div>

        <div v-else-if="selectedRun" class="row q-col-gutter-lg">
          <div class="col-12">
            <q-btn flat icon="arrow_back" color="primary" class="q-mb-md" @click="backToIndex">
              Back to open runs
            </q-btn>
          </div>

          <div class="col-12 col-xl-8">
            <q-card bordered class="q-mb-lg">
              <q-card-section class="row items-start justify-between q-col-gutter-md">
                <div class="col">
                  <div class="text-overline text-primary">Live Run</div>
                  <div class="text-h4 text-weight-bold" v-text="selectedRunTitle"></div>
                  <div class="text-subtitle2 q-mt-xs" v-text="selectedRunSubtitle"></div>
                  <div class="text-body2 q-mt-sm">
                    <span>Run </span>
                    <span v-text="selectedRun.id"></span>
                    <span> · Template </span>
                    <span v-text="selectedRun.game_id"></span>
                  </div>
                </div>
                <div class="col-auto">
                  <q-badge :color="statusColor(selectedRun.status)" class="q-px-md q-py-sm">
                    <span v-text="selectedRun.status"></span>
                  </q-badge>
                  <div class="text-caption q-mt-sm text-right">
                    Updated
                    <span v-text="formatDateFrom(selectedRun.updated_at)"></span>
                  </div>
                </div>
              </q-card-section>

              <q-separator></q-separator>

              <q-card-section>
                <div class="row items-center justify-between q-mb-md">
                  <div class="text-overline">Arena Map</div>
                  <q-chip dense outline icon="hub">
                    <span v-text="selectedRunMapSummary.total"></span>
                    <span> hexes</span>
                  </q-chip>
                </div>
                <div
                  v-if="selectedRunHasMap"
                  ref="arenaCanvasWrap"
                  class="hexarena-canvas-wrap row items-center justify-center"
                  style="min-height: 80vh; position: relative;"
                >
                  <canvas
                    ref="arenaCanvas"
                    class="hexarena-canvas"
                    @mousemove="handleCanvasMove"
                    @mouseleave="clearCanvasHover"
                  ></canvas>
                  <q-card
                    v-if="hoveredTile"
                    bordered
                    class="hexarena-hover-card"
                    :style="{
                      position: 'absolute',
                      left: `${hoverPosition.x}px`,
                      top: `${hoverPosition.y}px`,
                      width: '15rem',
                      pointerEvents: 'none',
                      zIndex: 2
                    }"
                  >
                    <q-card-section class="q-pa-sm">
                      <div class="text-overline text-primary">Hex</div>
                      <div class="text-subtitle2">
                        <span v-text="hoveredTile.id"></span>
                        <span> · </span>
                        <span v-text="hoveredTile.terrain"></span>
                      </div>
                      <q-list dense class="q-mt-sm">
                        <q-item class="q-px-none">
                          <q-item-section>
                            <q-item-label caption>Power</q-item-label>
                            <q-item-label v-text="hoveredTile.power"></q-item-label>
                          </q-item-section>
                          <q-item-section>
                            <q-item-label caption>Owner</q-item-label>
                            <q-item-label v-text="tileOwnerLabel(hoveredTile)"></q-item-label>
                          </q-item-section>
                        </q-item>
                        <q-item class="q-px-none">
                          <q-item-section>
                            <q-item-label caption>Coordinates</q-item-label>
                            <q-item-label>
                              <span v-text="hoveredTile.q"></span>
                              <span>, </span>
                              <span v-text="hoveredTile.r"></span>
                            </q-item-label>
                          </q-item-section>
                          <q-item-section>
                            <q-item-label caption>Adjacent</q-item-label>
                            <q-item-label v-text="hoveredTile.adjacent.length"></q-item-label>
                          </q-item-section>
                        </q-item>
                      </q-list>
                    </q-card-section>
                  </q-card>
                </div>
                <q-banner v-else-if="selectedRun.status === 'waiting'" rounded class="q-mt-sm">
                  This run has not started yet. The live arena will appear here once the match begins.
                </q-banner>
                <q-banner v-else rounded class="q-mt-sm">
                  Arena state is initializing. Refresh will happen automatically as the run updates.
                </q-banner>
                <div class="row q-col-gutter-sm q-mt-md">
                  <div class="col-12 col-sm-4">
                    <q-card bordered>
                      <q-card-section>
                        <div class="text-overline">Owned</div>
                        <div class="text-h6" v-text="selectedRunMapSummary.owned"></div>
                      </q-card-section>
                    </q-card>
                  </div>
                  <div class="col-12 col-sm-4">
                    <q-card bordered>
                      <q-card-section>
                        <div class="text-overline">Neutral</div>
                        <div class="text-h6" v-text="selectedRunMapSummary.neutral"></div>
                      </q-card-section>
                    </q-card>
                  </div>
                  <div class="col-12 col-sm-4">
                    <q-card bordered>
                      <q-card-section>
                        <div class="text-overline">Frontline</div>
                        <div class="text-h6" v-text="selectedRunMapSummary.contested"></div>
                      </q-card-section>
                    </q-card>
                  </div>
                </div>
              </q-card-section>

              <q-separator></q-separator>

              <q-card-section>
                <div class="row q-col-gutter-md">
                  <div class="col-12 col-sm-6 col-lg-3">
                    <q-card bordered>
                      <q-card-section>
                        <div class="text-overline">Entry Fee</div>
                        <div class="text-h6" v-text="formatSats(selectedRun.config.entry_fee_sats)"></div>
                      </q-card-section>
                    </q-card>
                  </div>
                  <div class="col-12 col-sm-6 col-lg-3">
                    <q-card bordered>
                      <q-card-section>
                        <div class="text-overline">Prize Pool</div>
                        <div class="text-h6" v-text="formatSats(selectedRun.prize_pool_sats)"></div>
                      </q-card-section>
                    </q-card>
                  </div>
                  <div class="col-12 col-sm-6 col-lg-3">
                    <q-card bordered>
                      <q-card-section>
                        <div class="text-overline">Players</div>
                        <div class="text-h6">
                          <span v-text="selectedRun.active_agent_count"></span>
                          <span>/</span>
                          <span v-text="selectedRun.config.max_players"></span>
                        </div>
                      </q-card-section>
                    </q-card>
                  </div>
                  <div class="col-12 col-sm-6 col-lg-3">
                    <q-card bordered>
                      <q-card-section>
                        <div class="text-overline">Turn Speed</div>
                        <div class="text-h6">
                          <span v-text="selectedRun.config.poll_interval_sec"></span>
                          <span> sec</span>
                        </div>
                      </q-card-section>
                    </q-card>
                  </div>
                </div>
              </q-card-section>
            </q-card>
          </div>

          <div class="col-12 col-xl-4">
            <q-card bordered class="q-mb-lg">
              <q-card-section>
                <div class="text-overline text-primary">Standings</div>
                <q-list separator class="q-mt-sm">
                  <q-item v-for="entry in selectedRunLeaderboard" :key="entry.agentId">
                    <q-item-section avatar>
                      <q-avatar :style="{ backgroundColor: ownerColor(entry.agentId), color: '#111827' }">
                        <span v-text="entry.rank"></span>
                      </q-avatar>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label v-text="entry.displayName || shortId(entry.agentId)"></q-item-label>
                      <q-item-label caption>
                        <span v-text="entry.hexes"></span>
                        <span> hexes · </span>
                        <span v-text="entry.totalPower"></span>
                        <span> power</span>
                      </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-chip
                        dense
                        :color="agentStatus(entry.agentId) === 'Active' ? 'positive' : 'negative'"
                        text-color="white"
                      >
                        <span v-text="agentStatus(entry.agentId)"></span>
                      </q-chip>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card bordered class="q-mb-lg">
              <q-card-section>
                <div class="text-overline text-primary">Board Legend</div>
                <q-list dense separator class="q-mt-sm">
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Number Inside Hex</q-item-label>
                      <q-item-label>Current power on that tile</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>F</q-item-label>
                      <q-item-label>Forest terrain</q-item-label>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label caption>M</q-item-label>
                      <q-item-label>Mountain terrain</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Dark muted hex</q-item-label>
                      <q-item-label>Water terrain</q-item-label>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label caption>Dashed white ring</q-item-label>
                      <q-item-label>Latest action target</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Extra glow</q-item-label>
                      <q-item-label>Current leader territory</q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card bordered class="q-mb-lg">
              <q-card-section>
                <div class="text-overline text-primary">Run Facts</div>
                <q-list dense separator class="q-mt-sm">
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Status</q-item-label>
                      <q-item-label v-text="selectedRun.status"></q-item-label>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label caption>Turn</q-item-label>
                      <q-item-label v-text="selectedRun.turn"></q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Open Seats</q-item-label>
                      <q-item-label v-text="selectedRun.open_seats"></q-item-label>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label caption>Starts On Join</q-item-label>
                      <q-item-label v-text="selectedRun.starts_on_join ? 'Yes' : 'No'"></q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Winner</q-item-label>
                      <q-item-label v-text="selectedRun.winner_agent_id || '-'"></q-item-label>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label caption>Updated</q-item-label>
                      <q-item-label v-text="formatDateFrom(selectedRun.updated_at)"></q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card bordered>
              <q-card-section>
                <div class="text-overline text-primary">Recent Actions</div>
                <q-banner v-if="latestAction" rounded class="q-mt-sm q-mb-md">
                  Latest move:
                  <strong v-text="actionSummary(latestAction)"></strong>
                </q-banner>
                <q-list separator class="q-mt-sm">
                  <q-item v-if="!selectedRunRecentActions.length">
                    <q-item-section>
                      <q-item-label>No public action log yet.</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-for="action in selectedRunRecentActions" :key="action.id || `${action.type}-${action.created_at}`">
                    <q-item-section side>
                      <q-chip dense :color="actionTypeColor(action.type)" text-color="white">
                        <span v-text="action.type"></span>
                      </q-chip>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label v-text="actionSummary(action)"></q-item-label>
                      <q-item-label caption v-text="formatDateFrom(action.created_at)"></q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card bordered class="q-mt-lg">
              <q-card-section>
                <div class="text-overline text-primary">Player Colors</div>
                <div class="row q-gutter-sm q-mt-sm">
                  <q-chip
                    v-for="entry in selectedRunLeaderboard"
                    :key="`legend-${entry.agentId}`"
                    square
                    :style="{ borderColor: ownerColor(entry.agentId), color: ownerColor(entry.agentId) }"
                    outline
                  >
                    <q-avatar :style="{ backgroundColor: ownerColor(entry.agentId), color: '#111827' }">
                      <span v-text="entry.rank"></span>
                    </q-avatar>
                    <span v-text="entry.displayName || shortId(entry.agentId)"></span>
                  </q-chip>
                </div>
              </q-card-section>
            </q-card>
          </div>
        </div>

        <div v-else>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6 col-xl-4" v-for="run in runList" :key="run.id">
              <q-card bordered class="cursor-pointer full-height" @click="selectRun(run)">
                <q-card-section>
                  <div class="row items-center justify-between no-wrap">
                    <div class="col">
                      <div class="text-overline text-primary">Open Run</div>
                      <div class="text-h6 text-weight-bold" v-text="run.game_name"></div>
                      <div class="text-caption q-mt-xs">
                        <span v-text="run.config.base_hex_count"></span>
                        <span> hexes · </span>
                        <span v-text="run.config.max_rounds"></span>
                        <span> max rounds</span>
                      </div>
                    </div>
                    <q-badge :color="statusColor(run.run_status)">
                      <span v-text="run.run_status"></span>
                    </q-badge>
                  </div>
                </q-card-section>

                <q-separator></q-separator>

                <q-card-section>
                  <q-list dense separator>
                    <q-item>
                      <q-item-section>
                        <q-item-label caption>Entry</q-item-label>
                        <q-item-label v-text="formatSats(run.config.entry_fee_sats)"></q-item-label>
                      </q-item-section>
                      <q-item-section>
                        <q-item-label caption>Prize Pool</q-item-label>
                        <q-item-label v-text="formatSats(run.prize_pool_sats)"></q-item-label>
                      </q-item-section>
                    </q-item>
                    <q-item>
                      <q-item-section>
                        <q-item-label caption>Players</q-item-label>
                        <q-item-label>
                          <span v-text="run.active_agent_count"></span>
                          <span>/</span>
                          <span v-text="run.config.max_players"></span>
                        </q-item-label>
                      </q-item-section>
                      <q-item-section>
                        <q-item-label caption>Turn Speed</q-item-label>
                        <q-item-label>
                          <span v-text="run.config.poll_interval_sec"></span>
                          <span> sec</span>
                        </q-item-label>
                      </q-item-section>
                    </q-item>
                    <q-item>
                      <q-item-section>
                        <q-item-label caption>Open Seats</q-item-label>
                        <q-item-label v-text="run.open_seats"></q-item-label>
                      </q-item-section>
                      <q-item-section>
                        <q-item-label caption>Can Start</q-item-label>
                        <q-item-label v-text="run.can_start_now ? 'Yes' : 'No'"></q-item-label>
                      </q-item-section>
                    </q-item>
                  </q-list>
                </q-card-section>

                <q-card-actions align="right">
                  <q-btn flat color="primary" label="View Arena" @click.stop="selectRun(run)"></q-btn>
                </q-card-actions>
              </q-card>
            </div>
          </div>

          <q-card v-if="!runList.length" bordered class="q-pa-xl text-center">
            <q-icon name="visibility" color="grey" size="4rem"></q-icon>
            <div class="text-h5 q-mt-md">No public arenas right now</div>
            <div class="text-body2">
              As soon as an operator opens a run, it will show up here for spectators.
            </div>
          </q-card>
        </div>
      </div>
    </div>
  </q-page>
</template>
