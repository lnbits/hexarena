<template id="page-hexarena">
  <div class="row q-col-gutter-md">
    <div class="col-12 col-lg-9">
      <q-card>
        <q-card-section class="flex items-center">
          <div>
            <div class="text-overline text-grey-7">HexArena</div>
            <div class="text-h5">Games, runs, joins, and payouts</div>
            <div class="text-subtitle2 text-grey-7">
              Admin console for reusable game templates and live run operations.
            </div>
          </div>
          <q-space></q-space>
          <div class="q-py-md">
            <q-btn
              color="primary"
              icon="add"
              label="New Game"
              @click="showNewGameForm"
            ></q-btn>
            <q-btn
              color="secondary"
              flat
              icon="flag"
              label="New Run"
              @click="showNewRunForm()"
            ></q-btn>
            <q-btn
              color="grey-7"
              flat
              icon="refresh"
              :loading="summaryLoading"
              @click="reloadAll"
            ></q-btn>
          </div>
        </q-card-section>
      </q-card>

      <div class="row q-col-gutter-md q-pt-md">
        <div class="col-12 col-sm-6 col-lg-3">
          <q-card class="flex column full-height">
            <q-card-section>
              <div class="text-overline text-grey-7">Games</div>
              <div
                class="text-h5"
                v-text="gamesTable.pagination.rowsNumber"
              ></div>
              <div class="text-caption text-grey-7">Reusable templates</div>
            </q-card-section>
          </q-card>
        </div>
        <div class="col-12 col-sm-6 col-lg-3">
          <q-card class="flex column full-height">
            <q-card-section>
              <div class="text-overline text-grey-7">Running</div>
              <div class="text-h5" v-text="runSummary.running"></div>
              <div class="text-caption text-grey-7">Live game runs</div>
            </q-card-section>
          </q-card>
        </div>
        <div class="col-12 col-sm-6 col-lg-3">
          <q-card class="flex column full-height">
            <q-card-section>
              <div class="text-overline text-grey-7">Agents</div>
              <div
                class="text-h5"
                v-text="agentsTable.pagination.rowsNumber"
              ></div>
              <div class="text-caption text-grey-7">Joined players</div>
            </q-card-section>
          </q-card>
        </div>
        <div class="col-12 col-sm-6 col-lg-3">
          <q-card class="flex column full-height">
            <q-card-section>
              <div class="text-overline text-grey-7">Join Requests</div>
              <div
                class="text-h5"
                v-text="joinRequestsTable.pagination.rowsNumber"
              ></div>
              <div class="text-caption text-grey-7">
                Pending or settled entry payments
              </div>
            </q-card-section>
          </q-card>
        </div>
      </div>

      <q-card class="q-mt-md">
        <q-card-section class="q-pb-none">
          <q-tabs
            v-model="activeTab"
            align="left"
            inline-label
            indicator-color="primary"
            active-color="primary"
          >
            <q-tab name="games" icon="sports_esports" label="Games"></q-tab>
            <q-tab name="runs" icon="hub" label="Runs"></q-tab>
            <q-tab name="agents" icon="smart_toy" label="Agents"></q-tab>
            <q-tab name="joins" icon="payments" label="Join Requests"></q-tab>
          </q-tabs>
        </q-card-section>
        <q-separator></q-separator>

        <q-tab-panels v-model="activeTab" animated>
          <q-tab-panel name="games">
            <div class="row q-col-gutter-md items-center q-mb-md">
              <div class="col-12 col-md">
                <q-input
                  v-model="gamesTable.search"
                  dense
                  debounce="300"
                  standout
                  placeholder="Search games"
                  @update:model-value="getGames"
                >
                  <template v-slot:append>
                    <q-icon name="search"></q-icon>
                  </template>
                </q-input>
              </div>
              <div class="col-12 col-md-auto row q-gutter-sm">
                <q-btn
                  color="primary"
                  unelevated
                  label="New Game"
                  @click="showNewGameForm"
                ></q-btn>
                <q-btn
                  flat
                  color="grey-7"
                  icon="file_download"
                  label="CSV"
                  @click="exportGamesCsv"
                ></q-btn>
              </div>
            </div>

            <q-table
              flat
              dense
              row-key="id"
              :rows="games"
              :columns="gamesTable.columns"
              v-model:pagination="gamesTable.pagination"
              :loading="gamesTable.loading"
              @request="getGames"
            >
              <template v-slot:header="props">
                <q-tr :props="props">
                  <q-th auto-width></q-th>
                  <q-th
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <span v-text="col.label"></span>
                  </q-th>
                </q-tr>
              </template>

              <template v-slot:body="props">
                <q-tr :props="props">
                  <q-td auto-width class="q-gutter-x-xs">
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="primary"
                      icon="add_circle"
                      @click="showNewRunForm(props.row.id)"
                    >
                      <q-tooltip>Create run from template</q-tooltip>
                    </q-btn>
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="secondary"
                      icon="edit"
                      @click="showEditGameForm(props.row)"
                    ></q-btn>
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="negative"
                      icon="delete"
                      @click="deleteGame(props.row.id)"
                    ></q-btn>
                  </q-td>
                  <q-td
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <div v-if="col.name === 'status'">
                      <q-chip
                        dense
                        square
                        :color="statusColor(props.row.status)"
                        text-color="white"
                      >
                        <span v-text="props.row.status"></span>
                      </q-chip>
                    </div>
                    <div v-else-if="col.name === 'wallet_id'">
                      <q-btn
                        flat
                        dense
                        no-caps
                        color="grey-8"
                        @click="copyText(props.row.wallet_id, 'Wallet ID')"
                      >
                        <span v-text="col.value"></span>
                      </q-btn>
                    </div>
                    <div v-else>
                      <span v-text="col.value"></span>
                    </div>
                  </q-td>
                </q-tr>
              </template>
            </q-table>
          </q-tab-panel>

          <q-tab-panel name="runs">
            <div class="row q-col-gutter-md items-center q-mb-md">
              <div class="col-12 col-md-4">
                <q-select
                  v-model="gameFilter"
                  dense
                  emit-value
                  map-options
                  clearable
                  filled
                  label="Filter by game"
                  :options="currentGameChoices"
                  @update:model-value="onGameFilterChanged"
                ></q-select>
              </div>
              <div class="col-12 col-md">
                <q-input
                  v-model="runsTable.search"
                  dense
                  debounce="300"
                  standout
                  placeholder="Search runs"
                  @update:model-value="getRuns"
                >
                  <template v-slot:append>
                    <q-icon name="search"></q-icon>
                  </template>
                </q-input>
              </div>
              <div class="col-12 col-md-auto row q-gutter-sm">
                <q-btn
                  color="primary"
                  unelevated
                  label="New Run"
                  @click="showNewRunForm(gameFilter || null)"
                ></q-btn>
                <q-btn
                  flat
                  color="grey-7"
                  icon="file_download"
                  label="CSV"
                  @click="exportRunsCsv"
                ></q-btn>
              </div>
            </div>

            <q-table
              flat
              dense
              row-key="id"
              :rows="runs"
              :columns="runsTable.columns"
              v-model:pagination="runsTable.pagination"
              :loading="runsTable.loading"
              @request="getRuns"
            >
              <template v-slot:header="props">
                <q-tr :props="props">
                  <q-th auto-width></q-th>
                  <q-th
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <span v-text="col.label"></span>
                  </q-th>
                </q-tr>
              </template>

              <template v-slot:body="props">
                <q-tr :props="props">
                  <q-td auto-width class="q-gutter-x-xs">
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="primary"
                      icon="launch"
                      @click="openPublicRun(props.row.id)"
                    >
                      <q-tooltip>Open public page</q-tooltip>
                    </q-btn>
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="secondary"
                      icon="edit"
                      @click="showEditRunForm(props.row)"
                    ></q-btn>
                    <q-btn
                      v-if="props.row.status === 'waiting'"
                      flat
                      dense
                      size="sm"
                      color="positive"
                      icon="play_arrow"
                      @click="startRun(props.row.id)"
                    ></q-btn>
                    <q-btn
                      v-if="props.row.status === 'running'"
                      flat
                      dense
                      size="sm"
                      color="warning"
                      icon="military_tech"
                      @click="openFinishRunDialog(props.row)"
                    ></q-btn>
                    <q-btn
                      v-if="['waiting', 'running'].includes(props.row.status)"
                      flat
                      dense
                      size="sm"
                      color="negative"
                      icon="stop_circle"
                      @click="cancelRun(props.row.id)"
                    ></q-btn>
                    <q-btn
                      v-if="
                        props.row.status === 'finished' &&
                        props.row.fee_status === 'failed'
                      "
                      flat
                      dense
                      size="sm"
                      color="warning"
                      icon="sync"
                      @click="retryRunFees(props.row.id)"
                    ></q-btn>
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="negative"
                      icon="delete"
                      @click="deleteRun(props.row.id)"
                    ></q-btn>
                  </q-td>
                  <q-td
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <div
                      v-if="col.name === 'status' || col.name === 'fee_status'"
                    >
                      <q-chip
                        dense
                        square
                        :color="statusColor(props.row[col.name])"
                        text-color="white"
                      >
                        <span v-text="props.row[col.name]"></span>
                      </q-chip>
                    </div>
                    <div v-else>
                      <span v-text="col.value"></span>
                    </div>
                  </q-td>
                </q-tr>
              </template>
            </q-table>
          </q-tab-panel>

          <q-tab-panel name="agents">
            <div class="row q-col-gutter-md items-center q-mb-md">
              <div class="col-12 col-md-3">
                <q-select
                  v-model="gameFilter"
                  dense
                  emit-value
                  map-options
                  clearable
                  filled
                  label="Filter by game"
                  :options="currentGameChoices"
                  @update:model-value="onGameFilterChanged"
                ></q-select>
              </div>
              <div class="col-12 col-md-3">
                <q-select
                  v-model="runFilter"
                  dense
                  emit-value
                  map-options
                  clearable
                  filled
                  label="Filter by run"
                  :options="currentRunChoices"
                  @update:model-value="onRunFilterChanged"
                ></q-select>
              </div>
              <div class="col-12 col-md">
                <q-input
                  v-model="agentsTable.search"
                  dense
                  debounce="300"
                  standout
                  placeholder="Search agents"
                  @update:model-value="getAgents"
                >
                  <template v-slot:append>
                    <q-icon name="search"></q-icon>
                  </template>
                </q-input>
              </div>
              <div class="col-12 col-md-auto">
                <q-btn
                  flat
                  color="grey-7"
                  icon="file_download"
                  label="CSV"
                  @click="exportAgentsCsv"
                ></q-btn>
              </div>
            </div>

            <q-table
              flat
              dense
              row-key="id"
              :rows="agents"
              :columns="agentsTable.columns"
              v-model:pagination="agentsTable.pagination"
              :loading="agentsTable.loading"
              @request="getAgents"
            >
              <template v-slot:header="props">
                <q-tr :props="props">
                  <q-th auto-width></q-th>
                  <q-th
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <span v-text="col.label"></span>
                  </q-th>
                </q-tr>
              </template>

              <template v-slot:body="props">
                <q-tr :props="props">
                  <q-td auto-width class="q-gutter-x-xs">
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="secondary"
                      icon="edit"
                      @click="showEditAgentForm(props.row)"
                    ></q-btn>
                    <q-btn
                      v-if="
                        props.row.payout_amount_sats > 0 &&
                        props.row.payout_status !== 'paid'
                      "
                      flat
                      dense
                      size="sm"
                      color="warning"
                      icon="payments"
                      @click="openPayoutDialog(props.row)"
                    ></q-btn>
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="negative"
                      icon="delete"
                      @click="deleteAgent(props.row.id)"
                    ></q-btn>
                  </q-td>
                  <q-td
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <div
                      v-if="
                        col.name === 'status' || col.name === 'payout_status'
                      "
                    >
                      <q-chip
                        dense
                        square
                        :color="statusColor(props.row[col.name])"
                        text-color="white"
                      >
                        <span v-text="props.row[col.name]"></span>
                      </q-chip>
                    </div>
                    <div v-else>
                      <span v-text="col.value"></span>
                    </div>
                  </q-td>
                </q-tr>
              </template>
            </q-table>
          </q-tab-panel>

          <q-tab-panel name="joins">
            <div class="row q-col-gutter-md items-center q-mb-md">
              <div class="col-12 col-md-3">
                <q-select
                  v-model="gameFilter"
                  dense
                  emit-value
                  map-options
                  clearable
                  filled
                  label="Filter by game"
                  :options="currentGameChoices"
                  @update:model-value="onGameFilterChanged"
                ></q-select>
              </div>
              <div class="col-12 col-md-3">
                <q-select
                  v-model="runFilter"
                  dense
                  emit-value
                  map-options
                  clearable
                  filled
                  label="Filter by run"
                  :options="currentRunChoices"
                  @update:model-value="onRunFilterChanged"
                ></q-select>
              </div>
              <div class="col-12 col-md">
                <q-input
                  v-model="joinRequestsTable.search"
                  dense
                  debounce="300"
                  standout
                  placeholder="Search join requests"
                  @update:model-value="getJoinRequests"
                >
                  <template v-slot:append>
                    <q-icon name="search"></q-icon>
                  </template>
                </q-input>
              </div>
              <div class="col-12 col-md-auto">
                <q-btn
                  flat
                  color="grey-7"
                  icon="file_download"
                  label="CSV"
                  @click="exportJoinRequestsCsv"
                ></q-btn>
              </div>
            </div>

            <q-table
              flat
              dense
              row-key="id"
              :rows="joinRequests"
              :columns="joinRequestsTable.columns"
              v-model:pagination="joinRequestsTable.pagination"
              :loading="joinRequestsTable.loading"
              @request="getJoinRequests"
            >
              <template v-slot:header="props">
                <q-tr :props="props">
                  <q-th auto-width></q-th>
                  <q-th
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <span v-text="col.label"></span>
                  </q-th>
                </q-tr>
              </template>

              <template v-slot:body="props">
                <q-tr :props="props">
                  <q-td auto-width class="q-gutter-x-xs">
                    <q-btn
                      flat
                      dense
                      size="sm"
                      color="grey-7"
                      icon="content_copy"
                      @click="copyText(props.row.id, 'Join request ID')"
                    ></q-btn>
                  </q-td>
                  <q-td
                    v-for="col in props.cols"
                    :key="col.name"
                    :props="props"
                  >
                    <div v-if="col.name === 'status'">
                      <q-chip
                        dense
                        square
                        :color="statusColor(props.row.status)"
                        text-color="white"
                      >
                        <span v-text="props.row.status"></span>
                      </q-chip>
                    </div>
                    <div v-else-if="col.name === 'paid'">
                      <q-chip
                        dense
                        square
                        :color="props.row.paid ? 'positive' : 'warning'"
                        text-color="white"
                      >
                        <span v-text="col.value"></span>
                      </q-chip>
                    </div>
                    <div v-else>
                      <span v-text="col.value"></span>
                    </div>
                  </q-td>
                </q-tr>
              </template>
            </q-table>
          </q-tab-panel>
        </q-tab-panels>
      </q-card>
    </div>

    <div class="col-12 col-lg-3 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <div class="text-overline text-grey-7">Run Status</div>
          <q-list dense separator>
            <q-item>
              <q-item-section>Waiting</q-item-section>
              <q-item-section side v-text="runSummary.waiting"></q-item-section>
            </q-item>
            <q-item>
              <q-item-section>Running</q-item-section>
              <q-item-section side v-text="runSummary.running"></q-item-section>
            </q-item>
            <q-item>
              <q-item-section>Finished</q-item-section>
              <q-item-section
                side
                v-text="runSummary.finished"
              ></q-item-section>
            </q-item>
            <q-item>
              <q-item-section>Cancelled</q-item-section>
              <q-item-section
                side
                v-text="runSummary.cancelled"
              ></q-item-section>
            </q-item>
          </q-list>
        </q-card-section>
      </q-card>

      <q-card>
        <q-card-section class="q-pa-none">
          <q-list>
            <q-expansion-item
              group="extras"
              icon="swap_vertical_circle"
              label="API info"
              :content-inset-level="0.5"
            >
              <q-btn
                flat
                label="Swagger API"
                type="a"
                target="_blank"
                href="../docs#/HexArena"
              ></q-btn>
            </q-expansion-item>
            <q-separator></q-separator>
            <q-expansion-item group="extras" icon="info" label="More info">
              <q-card>
                <q-card-section>
                  <p>Some more info about HexArena.</p>
                  <small>
                    Created by
                    <a
                      class="text-secondary"
                      href="https://github.com/lnbits"
                      target="_blank"
                    >
                      LNbits extension builder </a
                    >.
                  </small>
                </q-card-section>
              </q-card>
            </q-expansion-item>
          </q-list>
        </q-card-section>
      </q-card>
    </div>

    <q-dialog v-model="gameFormDialog.show" position="top">
      <q-card v-if="gameFormDialog.show" class="lnbits__dialog-card q-pa-lg">
        <q-card-section class="q-pa-none q-mb-md">
          <div
            class="text-h6"
            v-text="
              gameFormDialog.data.id
                ? 'Edit Game Template'
                : 'New Game Template'
            "
          ></div>
          <div class="text-caption text-grey-7">
            Reusable game definition with default run config.
          </div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="saveGame">
          <q-input
            filled
            dense
            v-model.trim="gameFormDialog.data.name"
            label="Name"
          ></q-input>
          <q-select
            filled
            dense
            emit-value
            map-options
            v-model="gameFormDialog.data.wallet_id"
            :options="g.user.walletOptions"
            label="Wallet"
          ></q-select>
          <q-select
            filled
            dense
            emit-value
            map-options
            clearable
            v-model="gameFormDialog.data.fee_wallet_id"
            :options="g.user.walletOptions"
            label="Optional fee wallet"
          ></q-select>
          <q-select
            filled
            dense
            v-model="gameFormDialog.data.status"
            :options="statusOptions.game"
            label="Status"
          ></q-select>
          <q-separator></q-separator>
          <div class="text-subtitle2">Default Run Config</div>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="gameFormDialog.data.default_config.min_players"
                label="Min players"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="gameFormDialog.data.default_config.max_players"
                label="Max players"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.entry_fee_sats
                "
                label="Entry fee (sats)"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.house_fee_percent
                "
                label="House fee %"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.poll_interval_sec
                "
                label="Poll interval sec"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.auto_start_after_sec
                "
                label="Auto-start after sec"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="gameFormDialog.data.default_config.max_rounds"
                label="Max rounds"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.base_hex_count
                "
                label="Base hex count"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.power_growth_every_n_turns
                "
                label="Power growth cadence"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.powerup_spawn_every_n_turns
                "
                label="Power-up spawn cadence"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  gameFormDialog.data.default_config.starting_power_new_hex
                "
                label="Starting power per new hex"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-select
                filled
                dense
                emit-value
                map-options
                v-model="gameFormDialog.data.default_config.payout_scheme"
                :options="payoutSchemeOptions"
                label="Payout scheme"
              ></q-select>
            </div>
            <div class="col-12 col-sm-6">
              <q-toggle
                v-model="gameFormDialog.data.default_config.enable_fortify"
                label="Enable fortify"
              ></q-toggle>
            </div>
            <div class="col-12 col-sm-6">
              <q-toggle
                v-model="gameFormDialog.data.default_config.pot_rollover"
                label="Pot rollover"
              ></q-toggle>
            </div>
          </div>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="primary"
              unelevated
              type="submit"
              label="Save"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="runFormDialog.show" position="top">
      <q-card v-if="runFormDialog.show" class="lnbits__dialog-card q-pa-lg">
        <q-card-section class="q-pa-none q-mb-md">
          <div
            class="text-h6"
            v-text="runFormDialog.data.id ? 'Edit Run' : 'Create Run'"
          ></div>
          <div class="text-caption text-grey-7">
            Run-scoped config derived from a reusable game template.
          </div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="saveRun">
          <q-select
            filled
            dense
            emit-value
            map-options
            v-model="runFormDialog.data.game_id"
            :options="currentGameChoices"
            label="Game template"
            :disable="!!runFormDialog.data.id"
            @update:model-value="onRunGameChanged"
          ></q-select>
          <q-select
            filled
            dense
            v-model="runFormDialog.data.status"
            :options="statusOptions.run"
            label="Status"
          ></q-select>
          <q-separator></q-separator>
          <div class="text-subtitle2">Run Config</div>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.min_players"
                label="Min players"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.max_players"
                label="Max players"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.entry_fee_sats"
                label="Entry fee (sats)"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.house_fee_percent"
                label="House fee %"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.poll_interval_sec"
                label="Poll interval sec"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.auto_start_after_sec"
                label="Auto-start after sec"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.max_rounds"
                label="Max rounds"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="runFormDialog.data.config.base_hex_count"
                label="Base hex count"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  runFormDialog.data.config.power_growth_every_n_turns
                "
                label="Power growth cadence"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  runFormDialog.data.config.powerup_spawn_every_n_turns
                "
                label="Power-up spawn cadence"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-input
                filled
                dense
                type="number"
                v-model.number="
                  runFormDialog.data.config.starting_power_new_hex
                "
                label="Starting power per new hex"
              ></q-input>
            </div>
            <div class="col-12 col-sm-6">
              <q-select
                filled
                dense
                emit-value
                map-options
                v-model="runFormDialog.data.config.payout_scheme"
                :options="payoutSchemeOptions"
                label="Payout scheme"
              ></q-select>
            </div>
            <div class="col-12 col-sm-6">
              <q-toggle
                v-model="runFormDialog.data.config.enable_fortify"
                label="Enable fortify"
              ></q-toggle>
            </div>
            <div class="col-12 col-sm-6">
              <q-toggle
                v-model="runFormDialog.data.config.pot_rollover"
                label="Pot rollover"
              ></q-toggle>
            </div>
          </div>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="primary"
              unelevated
              type="submit"
              label="Save"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="agentFormDialog.show" position="top">
      <q-card v-if="agentFormDialog.show" class="lnbits__dialog-card q-pa-lg">
        <q-card-section class="q-pa-none q-mb-md">
          <div class="text-h6">Edit Agent</div>
          <div class="text-caption text-grey-7">
            Admin-safe adjustments to a joined player.
          </div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="saveAgent">
          <q-input
            filled
            dense
            v-model.trim="agentFormDialog.data.display_name"
            label="Display name"
          ></q-input>
          <q-select
            filled
            dense
            v-model="agentFormDialog.data.status"
            :options="statusOptions.agent"
            label="Status"
          ></q-select>
          <q-input
            filled
            dense
            v-model.trim="agentFormDialog.data.payout_request"
            label="Payout request"
          ></q-input>
          <q-input
            filled
            dense
            autogrow
            type="textarea"
            v-model="agentFormDialog.data.inventory_text"
            label="Inventory JSON"
          ></q-input>
          <q-input
            filled
            dense
            autogrow
            type="textarea"
            v-model="agentFormDialog.data.profile_text"
            label="Profile JSON"
          ></q-input>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="primary"
              unelevated
              type="submit"
              label="Save"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="finishRunDialog.show" position="top">
      <q-card v-if="finishRunDialog.show" class="lnbits__dialog-card q-pa-lg">
        <q-card-section class="q-pa-none q-mb-md">
          <div class="text-h6">Finish Run</div>
          <div class="text-caption text-grey-7">
            Optionally force a specific winner agent before payout settlement.
          </div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="saveFinishRun">
          <q-select
            filled
            dense
            clearable
            emit-value
            map-options
            v-model="finishRunDialog.data.winner_agent_id"
            :options="
              agents
                .filter(agent => agent.run_id === finishRunDialog.data.run_id)
                .map(agent => ({
                  label: agent.display_name || agent.id,
                  value: agent.id
                }))
            "
            label="Winner agent"
          ></q-select>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="warning"
              unelevated
              type="submit"
              label="Finish run"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="payoutDialog.show" position="top">
      <q-card v-if="payoutDialog.show" class="lnbits__dialog-card q-pa-lg">
        <q-card-section class="q-pa-none q-mb-md">
          <div class="text-h6">Settle Agent Payout</div>
          <div class="text-caption text-grey-7">
            Manual payout fallback using a lightning invoice.
          </div>
        </q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="settlePayout">
          <q-input
            filled
            dense
            autogrow
            type="textarea"
            v-model.trim="payoutDialog.data.payment_request"
            label="Payment request"
          ></q-input>
          <q-card-actions align="right" class="q-px-none q-pb-none">
            <q-btn flat color="grey-7" v-close-popup label="Cancel"></q-btn>
            <q-btn
              color="primary"
              unelevated
              type="submit"
              label="Settle payout"
            ></q-btn>
          </q-card-actions>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>
