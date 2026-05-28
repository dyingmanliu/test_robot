<template>
  <div class="kb-page">
    <header class="head">
      <div>
        <h1>项目知识库</h1>
        <p v-if="project" class="sub">{{ project.name }} · 被测应用：{{ project.tested_app_name || "无" }}</p>
      </div>
      <div class="head-actions">
        <router-link
          v-if="projectId"
          class="kb-link-btn"
          :to="{ name: 'projectDashboard', params: { projectId } }"
        >
          ← 项目看板
        </router-link>
      </div>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="msg" class="banner ok">{{ msg }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <template v-else-if="projectId">
      <div class="kb-layout">
        <!-- 左侧：知识集合 -->
        <aside class="kb-sidebar card">
          <div class="sidebar-head">
            <h2>知识集合</h2>
            <button type="button" class="kb-toolbar-btn kb-toolbar-btn--primary" @click="openCollectionDialog">
              新建
            </button>
          </div>
          <ul v-if="collections.length" class="coll-list">
            <li v-for="c in collections" :key="c.id">
              <button
                type="button"
                class="coll-item"
                :class="{ active: selectedCollectionId === c.id }"
                @click="selectCollection(c.id)"
              >
                <span class="coll-name">{{ c.name }}</span>
                <span v-if="c.description" class="coll-desc">{{ c.description }}</span>
              </button>
            </li>
          </ul>
          <div v-else class="sidebar-empty">
            <p class="muted small">暂无集合</p>
            <button type="button" class="kb-btn kb-btn--primary" @click="openCollectionDialog">新建集合</button>
          </div>

          <div class="sidebar-settings">
            <div class="sidebar-settings-head">
              <h3>索引设置</h3>
              <span v-if="chunkPolicy.has_project_override" class="settings-badge">已自定义</span>
            </div>
            <p class="hint small settings-hint">影响切片与检索阈值；修改后请对已有文档「重建索引」。</p>
            <div class="settings-grid">
              <label class="settings-field">
                <span>切片长度</span>
                <input v-model.number="chunkPolicy.max_chars" type="number" min="200" max="4000" step="50" />
              </label>
              <label class="settings-field">
                <span>重叠字符</span>
                <input v-model.number="chunkPolicy.overlap" type="number" min="0" max="800" step="10" />
              </label>
              <label class="settings-field">
                <span>短文档重叠</span>
                <input v-model.number="chunkPolicy.overlap_short" type="number" min="0" max="400" step="10" />
              </label>
              <label class="settings-field">
                <span>最低相似度</span>
                <input
                  v-model="chunkPolicy.search_min_score_text"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  placeholder="留空用环境默认"
                />
              </label>
            </div>
            <div class="settings-checks">
              <label class="settings-check">
                <input v-model="chunkPolicy.prefix_title" type="checkbox" />
                向量前加文档标题
              </label>
              <label class="settings-check">
                <input v-model="chunkPolicy.prefix_section" type="checkbox" />
                向量前加章节标题
              </label>
              <label class="settings-check">
                <input v-model="chunkPolicy.heading_aware" type="checkbox" />
                按章节标题切片
              </label>
            </div>
            <div class="settings-actions">
              <button
                type="button"
                class="kb-toolbar-btn kb-toolbar-btn--primary"
                :disabled="chunkPolicySaving"
                @click="saveChunkPolicy"
              >
                {{ chunkPolicySaving ? "保存中…" : "保存" }}
              </button>
              <button
                v-if="chunkPolicy.has_project_override"
                type="button"
                class="kb-toolbar-btn"
                :disabled="chunkPolicySaving"
                @click="resetChunkPolicy"
              >
                恢复默认
              </button>
            </div>
          </div>
        </aside>

        <!-- 右侧：主工作区 -->
        <main class="kb-main">
          <div v-if="!selectedCollectionId" class="card main-empty">
            <div class="empty-icon">📚</div>
            <h3>选择或新建知识集合</h3>
            <p class="muted">在左侧选择已有集合，或点击「新建」开始管理文档与检索。</p>
            <button type="button" class="kb-btn kb-btn--primary" @click="openCollectionDialog">新建知识集合</button>
          </div>

          <template v-else>
            <div class="main-head card">
              <div>
                <div class="main-head-title-row">
                  <h2>{{ selectedCollection?.name }}</h2>
                  <span
                    v-if="selectedCollection"
                    class="status-chip"
                    :class="collectionStatusClass(selectedCollection.status)"
                    :title="`集合状态：${collectionStatusLabel(selectedCollection.status)}`"
                  >
                    <span class="status-dot" aria-hidden="true"></span>
                    {{ collectionStatusLabel(selectedCollection.status) }}
                  </span>
                </div>
                <p v-if="selectedCollection?.description" class="muted small">{{ selectedCollection.description }}</p>
                <div
                  v-if="selectedCollectionDocSummary.length"
                  class="coll-doc-summary"
                  aria-label="文档状态统计"
                >
                  <span
                    v-for="item in selectedCollectionDocSummary"
                    :key="item.status"
                    class="status-chip"
                    :class="item.class"
                    :title="`${item.label} ${item.count} 篇`"
                  >
                    <span class="status-dot" aria-hidden="true"></span>
                    {{ item.label }}
                    <span class="status-chip-count">{{ item.count }}</span>
                  </span>
                </div>
              </div>
              <div class="main-head-actions">
                <button type="button" class="kb-toolbar-btn" @click="openEditDialog">编辑</button>
                <button
                  type="button"
                  class="kb-toolbar-btn kb-toolbar-btn--danger"
                  :disabled="deletingCollection"
                  @click="openDeleteDialog"
                >
                  删除
                </button>
              </div>
            </div>

            <nav class="tab-bar card">
              <button
                type="button"
                class="tab"
                :class="{ active: activeTab === 'docs' }"
                @click="activeTab = 'docs'"
              >
                文档列表
                <span v-if="documents.length" class="tab-badge">{{ documents.length }}</span>
              </button>
              <button
                type="button"
                class="tab"
                :class="{ active: activeTab === 'add' }"
                @click="activeTab = 'add'"
              >
                添加内容
              </button>
              <button
                type="button"
                class="tab"
                :class="{ active: activeTab === 'search' }"
                @click="activeTab = 'search'"
              >
                检索测试
              </button>
            </nav>

            <!-- 文档列表 -->
            <section v-show="activeTab === 'docs'" class="card block">
              <p class="hint small doc-hint">
                仅<strong>已发布</strong>文档参与检索；
                <strong>索引中</strong>请稍候；
                <strong>待审核</strong>需
                <router-link v-if="canReview" :to="{ name: 'knowledgeReview' }">知识库审核</router-link>
                <template v-else>平台管理员在顶栏「后台管理 → 知识库审核」</template>
                通过后再检索。
              </p>
              <div class="filter-row">
                <label class="filter-label">
                  <span>类型筛选</span>
                  <select v-model="filterDocType" @change="loadDocuments">
                    <option value="">全部类型</option>
                    <option v-for="(label, key) in DOC_TYPE_LABELS" :key="key" :value="key">
                      {{ label }}
                    </option>
                  </select>
                </label>
                <button type="button" class="kb-toolbar-btn" @click="activeTab = 'add'">添加文档</button>
              </div>
              <ul v-if="documents.length" class="doc-list">
                <li v-for="d in documents" :key="d.id" class="doc-item">
                  <div class="doc-main">
                    <div class="doc-title">{{ d.title }}</div>
                    <div class="doc-meta">
                      <span class="type-tag">{{ docTypeLabel(d.doc_type) }}</span>
                      <span class="status-tag" :class="docStatusClass(d.status)">
                        <span class="status-dot" aria-hidden="true"></span>
                        {{ docStatusLabel(d.status) }}
                      </span>
                      <span v-if="d.has_chunk_override" class="custom-index-tag" title="使用单独索引参数">
                        自定义索引
                      </span>
                      <span v-if="d.updated_at" class="doc-time muted small">
                        更新 {{ formatTime(d.updated_at) }}
                      </span>
                    </div>
                  </div>
                  <div class="doc-actions">
                    <button
                      v-if="canSubmitReview(d.status)"
                      type="button"
                      class="kb-action-btn"
                      @click="submitDocReview(d.id)"
                    >
                      提交审核
                    </button>
                    <button type="button" class="kb-action-btn" @click="openDocChunkDialog(d)">
                      索引设置
                    </button>
                    <button
                      v-if="canReindex(d.status)"
                      type="button"
                      class="kb-action-btn"
                      @click="reindexDoc(d.id)"
                    >
                      重建索引
                    </button>
                    <span v-else-if="reindexBlockHint(d.status)" class="reindex-hint muted small">
                      {{ reindexBlockHint(d.status) }}
                    </span>
                    <button
                      type="button"
                      class="kb-action-btn kb-action-btn--danger"
                      @click="openDeleteDocDialog(d)"
                    >
                      删除
                    </button>
                  </div>
                </li>
              </ul>
              <div v-else class="empty-doc">
                <p class="muted">该集合暂无文档</p>
                <button type="button" class="kb-btn kb-btn--primary" @click="activeTab = 'add'">上传或录入</button>
              </div>
            </section>

            <!-- 添加内容 -->
            <section v-show="activeTab === 'add'" class="card block">
              <div class="add-tabs">
                <button
                  type="button"
                  class="add-tab"
                  :class="{ active: addMode === 'upload' }"
                  @click="addMode = 'upload'"
                >
                  上传文件
                </button>
                <button
                  type="button"
                  class="add-tab"
                  :class="{ active: addMode === 'structured' }"
                  @click="addMode = 'structured'"
                >
                  结构化录入
                </button>
              </div>

              <div v-show="addMode === 'upload'" class="add-panel">
                <h3 class="upload-section-title">上传文本文件</h3>
                <div class="upload-options">
                  <label class="upload-option">
                    <span>文档类型</span>
                    <select v-model="upload.doc_type">
                      <option v-for="(label, key) in uploadDocTypes" :key="key" :value="key">{{ label }}</option>
                    </select>
                  </label>
                  <label class="upload-option">
                    <span>标题（可选）</span>
                    <input v-model="upload.title" maxlength="512" placeholder="留空则使用文件名" />
                  </label>
                </div>

                <div
                  class="upload-dropzone"
                  :class="{ 'upload-dropzone--active': uploadDragOver, 'upload-dropzone--has-file': upload.file }"
                  @dragover.prevent="uploadDragOver = true"
                  @dragleave.prevent="uploadDragOver = false"
                  @drop.prevent="onFileDrop"
                  @click="triggerFileSelect"
                >
                  <input
                    ref="fileInputRef"
                    type="file"
                    class="upload-input-hidden"
                    accept=".txt,.md,.markdown,.mdx,.pdf,.html,.htm,.xlsx,.xls,.docx,.csv,.json"
                    @change="onFileChange"
                  />
                  <div v-if="!upload.file" class="dropzone-empty">
                    <div class="dropzone-icon" aria-hidden="true">☁️</div>
                    <p class="dropzone-text">
                      拖拽文件至此，或者
                      <button type="button" class="dropzone-link" @click.stop="triggerFileSelect">选择文件</button>
                    </p>
                    <p class="dropzone-hint">{{ UPLOAD_HINT }} 测试规范/策略上传后需平台管理员审核。</p>
                  </div>
                  <div v-else class="dropzone-file" @click.stop>
                    <div class="file-icon" :class="fileIconClass(upload.file.name)">{{ fileExtLabel(upload.file.name) }}</div>
                    <div class="file-info">
                      <div class="file-name" :title="upload.file.name">{{ upload.file.name }}</div>
                      <div class="file-meta">{{ fileExtLabel(upload.file.name) }} · {{ formatFileSize(upload.file.size) }}</div>
                    </div>
                    <button type="button" class="file-remove" title="移除" @click="clearUploadFile">🗑</button>
                  </div>
                </div>

                <div class="upload-advanced">
                  <button
                    type="button"
                    class="upload-advanced-toggle"
                    @click="uploadAdvancedOpen = !uploadAdvancedOpen"
                  >
                    {{ uploadAdvancedOpen ? "▼" : "▶" }} 高级索引选项（仅本文件）
                  </button>
                  <div v-show="uploadAdvancedOpen" class="upload-advanced-panel">
                    <label class="chunk-mode-option">
                      <input v-model="uploadChunkMode" type="radio" value="project" />
                      使用项目默认
                      <span class="muted small">（{{ projectChunkSummary }}）</span>
                    </label>
                    <label class="chunk-mode-option">
                      <input v-model="uploadChunkMode" type="radio" value="custom" @change="syncUploadChunkFromProject" />
                      本文件单独设置
                    </label>
                    <div v-if="uploadChunkMode === 'custom'" class="chunk-fields">
                      <div class="settings-grid">
                        <label class="settings-field">
                          <span>切片长度</span>
                          <input v-model.number="uploadChunk.max_chars" type="number" min="200" max="4000" step="50" />
                        </label>
                        <label class="settings-field">
                          <span>重叠字符</span>
                          <input v-model.number="uploadChunk.overlap" type="number" min="0" max="800" step="10" />
                        </label>
                        <label class="settings-field">
                          <span>短文档重叠</span>
                          <input v-model.number="uploadChunk.overlap_short" type="number" min="0" max="400" step="10" />
                        </label>
                      </div>
                      <div class="settings-checks">
                        <label class="settings-check">
                          <input v-model="uploadChunk.prefix_title" type="checkbox" />
                          向量前加文档标题
                        </label>
                        <label class="settings-check">
                          <input v-model="uploadChunk.prefix_section" type="checkbox" />
                          向量前加章节标题
                        </label>
                        <label class="settings-check">
                          <input v-model="uploadChunk.heading_aware" type="checkbox" />
                          按章节标题切片
                        </label>
                      </div>
                      <p class="hint small">最低相似度请在左侧「索引设置」配置（项目级）。</p>
                    </div>
                  </div>
                </div>

                <div class="upload-footer">
                  <button
                    type="button"
                    class="kb-btn kb-btn--primary"
                    :disabled="uploading || !upload.file"
                    @click="submitUpload"
                  >
                    {{ uploading ? "上传并索引中…" : "上传并索引" }}
                  </button>
                </div>
              </div>

              <div v-show="addMode === 'structured'" class="add-panel">
                <div class="form-grid">
                  <label class="field">
                    <span>类型</span>
                    <select v-model="structured.doc_type">
                      <option value="page_model">页面模型</option>
                      <option value="ui_element">UI 元素</option>
                      <option value="execution_hint">执行经验</option>
                    </select>
                  </label>
                  <label class="field">
                    <span>标题</span>
                    <input v-model="structured.title" maxlength="512" />
                  </label>
                  <label class="field full">
                    <span>JSON 内容</span>
                    <textarea
                      v-model="structured.jsonText"
                      rows="8"
                      placeholder='{"page_name":"","elements":[]}'
                    />
                  </label>
                </div>
                <button type="button" class="kb-btn kb-btn--primary" :disabled="structSaving" @click="submitStructured">
                  {{ structSaving ? "保存中…" : "保存并索引" }}
                </button>
              </div>
            </section>

            <!-- 检索测试 -->
            <section v-show="activeTab === 'search'" class="card block">
              <p class="hint small">
                输入自然语言问题，在当前项目知识库中做语义检索（需文档为<strong>已发布</strong>且已完成向量索引）。
              </p>
              <div class="search-row">
                <input v-model="searchQ" placeholder="输入检索问题…" @keyup.enter="runSearch" />
                <button type="button" class="kb-btn kb-btn--primary" :disabled="searching" @click="runSearch">
                  {{ searching ? "检索中…" : "检索" }}
                </button>
              </div>
              <p v-if="lastSearchQuery" class="hint small search-meta">
                检索词：<strong>{{ lastSearchQuery }}</strong>
                <span v-if="searchDone"> · 命中 {{ searchResults.length }} 条</span>
                <span v-if="searchMinScore != null"> · 最低相似度 ≥ {{ formatScore(searchMinScore) }}</span>
                <span v-if="searchLatencyMs != null"> · {{ searchLatencyMs }} ms</span>
              </p>
              <p v-if="searchDone && !searchResults.length" class="hint small warn">
                未命中结果。请确认文档为「已发布」、Embedding 与 Qdrant 正常；可在文档列表点「重建索引」后重试。
                <span v-if="searchMinScore != null"> 当前最低相似度 {{ formatScore(searchMinScore) }}，可在左侧「索引设置」或 web/backend/.env 的 KB_SEARCH_MIN_SCORE 调整。</span>
              </p>
              <div v-if="searchResults.length" class="hits">
                <article v-for="h in searchResults" :key="`${h.chunk_id}-${lastSearchQuery}`" class="hit">
                  <h4>
                    {{ docTypeLabel(h.doc_type) }} · {{ h.title }}
                    <span v-if="h.score != null" class="hit-score">{{ formatScore(h.score) }}</span>
                  </h4>
                  <p>{{ h.snippet }}</p>
                </article>
              </div>
            </section>
          </template>
        </main>
      </div>
    </template>

    <Teleport to="body">
      <div
        v-if="docChunkDialog.open"
        class="kb-modal-overlay"
        @click.self="docChunkDialog.open = false"
      >
        <div class="kb-modal kb-modal-wide" role="dialog" aria-modal="true">
          <h3>文档索引设置</h3>
          <p class="modal-desc muted small">{{ docChunkDialog.title }}</p>
          <label class="chunk-mode-option">
            <input v-model="docChunkDialog.mode" type="radio" value="project" />
            使用项目默认
          </label>
          <label class="chunk-mode-option">
            <input v-model="docChunkDialog.mode" type="radio" value="custom" />
            单独设置（仅影响本文件切片）
          </label>
          <div v-if="docChunkDialog.mode === 'custom'" class="chunk-fields">
            <div class="settings-grid">
              <label class="settings-field">
                <span>切片长度</span>
                <input v-model.number="docChunkDialog.max_chars" type="number" min="200" max="4000" step="50" />
              </label>
              <label class="settings-field">
                <span>重叠字符</span>
                <input v-model.number="docChunkDialog.overlap" type="number" min="0" max="800" step="10" />
              </label>
              <label class="settings-field">
                <span>短文档重叠</span>
                <input v-model.number="docChunkDialog.overlap_short" type="number" min="0" max="400" step="10" />
              </label>
            </div>
            <div class="settings-checks">
              <label class="settings-check">
                <input v-model="docChunkDialog.prefix_title" type="checkbox" />
                向量前加文档标题
              </label>
              <label class="settings-check">
                <input v-model="docChunkDialog.prefix_section" type="checkbox" />
                向量前加章节标题
              </label>
              <label class="settings-check">
                <input v-model="docChunkDialog.heading_aware" type="checkbox" />
                按章节标题切片
              </label>
            </div>
          </div>
          <p v-if="docChunkDialog.search_min_score != null" class="hint small">
            检索最低相似度（项目级）：{{ formatScore(docChunkDialog.search_min_score) }}
          </p>
          <p v-if="docChunkDialog.err" class="err">{{ docChunkDialog.err }}</p>
          <div class="modal-actions">
            <button type="button" class="kb-modal-btn" @click="docChunkDialog.open = false">取消</button>
            <button
              type="button"
              class="kb-modal-btn kb-modal-btn--primary"
              :disabled="docChunkDialog.saving"
              @click="saveDocChunkPolicy(false)"
            >
              {{ docChunkDialog.saving ? "保存中…" : "保存" }}
            </button>
            <button
              v-if="canReindex(docChunkDialog.status)"
              type="button"
              class="kb-modal-btn kb-modal-btn--primary"
              :disabled="docChunkDialog.saving"
              @click="saveDocChunkPolicy(true)"
            >
              保存并重建索引
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="deleteDocDialog.open"
        class="kb-modal-overlay"
        @click.self="deleteDocDialog.open = false"
      >
        <div class="kb-modal kb-modal-danger" role="dialog" aria-modal="true">
          <h3>删除文档</h3>
          <p class="modal-desc">
            确定删除「<strong>{{ deleteDocDialog.title }}</strong>」吗？
          </p>
          <p class="warn-box small">
            将同时删除向量索引、切片与上传文件，不可恢复。
          </p>
          <p v-if="deleteDocDialog.err" class="err">{{ deleteDocDialog.err }}</p>
          <div class="modal-actions">
            <button type="button" class="kb-modal-btn" @click="deleteDocDialog.open = false">取消</button>
            <button
              type="button"
              class="kb-modal-btn kb-modal-btn--danger"
              :disabled="deletingDoc"
              @click="confirmDeleteDocument"
            >
              {{ deletingDoc ? "删除中…" : "确认删除" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="deleteDialog.open"
        class="kb-modal-overlay"
        @click.self="deleteDialog.open = false"
      >
        <div class="kb-modal kb-modal-danger" role="dialog" aria-modal="true">
          <h3>删除知识集合</h3>
          <p class="modal-desc">
            确定删除「<strong>{{ deleteDialog.name }}</strong>」吗？
          </p>
          <p v-if="deleteDialog.docCount > 0" class="warn-box small">
            该集合含 {{ deleteDialog.docCount }} 篇文档，删除后文档、向量索引与上传文件均不可恢复。
          </p>
          <p v-else class="muted small">该集合暂无文档，删除后不可恢复。</p>
          <p v-if="deleteDialog.err" class="err">{{ deleteDialog.err }}</p>
          <div class="modal-actions">
            <button type="button" class="kb-modal-btn" @click="deleteDialog.open = false">取消</button>
            <button type="button" class="kb-modal-btn kb-modal-btn--danger" :disabled="deletingCollection" @click="confirmDeleteCollection">
              {{ deletingCollection ? "删除中…" : "确认删除" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="collDialog.open"
        class="kb-modal-overlay"
        @click.self="collDialog.open = false"
      >
        <div class="kb-modal" role="dialog" aria-modal="true" aria-labelledby="coll-dialog-title">
          <h3 id="coll-dialog-title">{{ collDialog.mode === "edit" ? "编辑知识集合" : "新建知识集合" }}</h3>
          <p class="modal-desc muted small">
            {{
              collDialog.mode === "edit"
                ? "修改集合名称与描述，不影响已有文档与索引。"
                : "集合用于分组管理文档，创建后可在右侧上传与检索。"
            }}
          </p>
          <label class="field">
            <span>名称</span>
            <input
              ref="collNameInput"
              v-model="collDialog.name"
              maxlength="256"
              placeholder="例如：登录模块规范"
              @keyup.enter="saveCollection"
            />
          </label>
          <label class="field">
            <span>描述（可选）</span>
            <textarea v-model="collDialog.description" rows="3" placeholder="简要说明该集合用途" />
          </label>
          <p v-if="collDialog.err" class="err">{{ collDialog.err }}</p>
          <div class="modal-actions">
            <button type="button" class="kb-modal-btn" @click="collDialog.open = false">取消</button>
            <button type="button" class="kb-modal-btn kb-modal-btn--primary" :disabled="collSaving" @click="saveCollection">
              {{ collSaving ? "保存中…" : collDialog.mode === "edit" ? "保存" : "创建" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import {
  DOC_TYPE_LABELS,
  collectionStatusClass,
  collectionStatusLabel,
  docStatusClass,
  docStatusLabel,
  docStatusSummaryItems,
  docTypeLabel,
  canReindex,
  reindexBlockHint,
} from "@/utils/knowledgeLabels";
import {
  isAllowedUploadFile,
  UPLOAD_HINT,
  validateUploadFileSize,
  MAX_UPLOAD_BYTES,
} from "@/utils/knowledgeUpload";

const route = useRoute();
const auth = useAuthStore();
const canReview = computed(() => auth.role === "platform_admin");
const projectId = computed(() => Number(route.params.projectId) || 0);

const project = ref(null);
const collections = ref([]);
const documents = ref([]);
const selectedCollectionId = ref(null);
const activeTab = ref("docs");
const addMode = ref("upload");
const loading = ref(true);
const error = ref("");
const msg = ref("");
const filterDocType = ref("");
const searchQ = ref("");
const searchResults = ref([]);
const searchDone = ref(false);
const searching = ref(false);
const lastSearchQuery = ref("");
const searchLatencyMs = ref(null);
const searchMinScore = ref(null);
const uploading = ref(false);
const structSaving = ref(false);
const collSaving = ref(false);
const deletingCollection = ref(false);
const deletingDoc = ref(false);
const collNameInput = ref(null);
const fileInputRef = ref(null);
const uploadDragOver = ref(false);

const chunkPolicy = reactive({
  max_chars: 800,
  overlap: 100,
  overlap_short: 80,
  prefix_title: true,
  prefix_section: true,
  heading_aware: true,
  search_min_score_text: "",
  has_project_override: false,
});
const chunkPolicySaving = ref(false);
const uploadAdvancedOpen = ref(false);
const uploadChunkMode = ref("project");
const uploadChunk = reactive({
  max_chars: 800,
  overlap: 100,
  overlap_short: 80,
  prefix_title: true,
  prefix_section: true,
  heading_aware: true,
});

const uploadDocTypes = {
  standard: "测试规范",
  strategy: "测试策略",
  page_model: "页面模型",
  ui_element: "UI 元素",
  glossary: "术语表",
  execution_hint: "执行经验",
  other: "其他",
};

const upload = reactive({ doc_type: "standard", title: "", file: null });
const structured = reactive({
  doc_type: "page_model",
  title: "",
  jsonText: '{"page_name":"","description":"","elements":[]}',
});

const collDialog = reactive({
  open: false,
  mode: "create",
  id: null,
  name: "",
  description: "",
  err: "",
});
const deleteDialog = reactive({ open: false, id: null, name: "", docCount: 0, err: "" });
const deleteDocDialog = reactive({ open: false, id: null, title: "", err: "" });
const docChunkDialog = reactive({
  open: false,
  docId: null,
  title: "",
  status: "",
  mode: "project",
  saving: false,
  err: "",
  max_chars: 800,
  overlap: 100,
  overlap_short: 80,
  prefix_title: true,
  prefix_section: true,
  heading_aware: true,
  search_min_score: null,
});

const projectChunkSummary = computed(() => {
  const parts = [`切片 ${chunkPolicy.max_chars}`, `重叠 ${chunkPolicy.overlap}`];
  if (chunkPolicy.heading_aware) parts.push("按章节切片");
  return parts.join(" · ");
});

const selectedCollection = computed(() =>
  collections.value.find((c) => c.id === selectedCollectionId.value) || null,
);

const selectedCollectionDocSummary = computed(() =>
  docStatusSummaryItems(selectedCollection.value?.doc_status_counts),
);

async function refreshKnowledgeDocs() {
  await Promise.all([loadDocuments(), loadCollections()]);
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** 仅草稿、已驳回可主动提交审核；已发布/待审核/索引中不再显示按钮 */
function canSubmitReview(status) {
  return status === "draft" || status === "rejected";
}

async function loadProject() {
  if (!projectId.value) return;
  const { data } = await client.get(`/api/projects/${projectId.value}`);
  project.value = data;
}

async function loadCollections() {
  const { data } = await client.get(`/api/knowledge/projects/${projectId.value}/collections`);
  collections.value = data;
  if (!selectedCollectionId.value && data.length) {
    selectedCollectionId.value = data[0].id;
  }
}

async function loadDocuments() {
  if (!projectId.value) return;
  const params = {};
  if (selectedCollectionId.value) params.collection_id = selectedCollectionId.value;
  if (filterDocType.value) params.doc_type = filterDocType.value;
  const { data } = await client.get(`/api/knowledge/projects/${projectId.value}/documents`, { params });
  documents.value = data;
}

async function loadChunkPolicy() {
  if (!projectId.value) return;
  const { data } = await client.get(`/api/knowledge/projects/${projectId.value}/chunk-policy`);
  chunkPolicy.max_chars = data.max_chars;
  chunkPolicy.overlap = data.overlap;
  chunkPolicy.overlap_short = data.overlap_short;
  chunkPolicy.prefix_title = data.prefix_title;
  chunkPolicy.prefix_section = data.prefix_section;
  chunkPolicy.heading_aware = data.heading_aware;
  chunkPolicy.search_min_score_text =
    data.search_min_score != null && data.search_min_score !== "" ? String(data.search_min_score) : "";
  chunkPolicy.has_project_override = Boolean(data.has_project_override);
}

async function saveChunkPolicy() {
  chunkPolicySaving.value = true;
  error.value = "";
  try {
    const body = {
      max_chars: chunkPolicy.max_chars,
      overlap: chunkPolicy.overlap,
      overlap_short: chunkPolicy.overlap_short,
      prefix_title: chunkPolicy.prefix_title,
      prefix_section: chunkPolicy.prefix_section,
      heading_aware: chunkPolicy.heading_aware,
    };
    const scoreText = String(chunkPolicy.search_min_score_text ?? "").trim();
    body.search_min_score = scoreText === "" ? null : Number(scoreText);
    const { data } = await client.patch(`/api/knowledge/projects/${projectId.value}/chunk-policy`, body);
    chunkPolicy.has_project_override = Boolean(data.has_project_override);
    msg.value = "索引设置已保存；请对已发布文档执行「重建索引」使切片生效";
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    chunkPolicySaving.value = false;
  }
}

async function resetChunkPolicy() {
  chunkPolicySaving.value = true;
  error.value = "";
  try {
    await client.delete(`/api/knowledge/projects/${projectId.value}/chunk-policy`);
    await loadChunkPolicy();
    msg.value = "已恢复环境默认索引设置";
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    chunkPolicySaving.value = false;
  }
}

function syncUploadChunkFromProject() {
  uploadChunk.max_chars = chunkPolicy.max_chars;
  uploadChunk.overlap = chunkPolicy.overlap;
  uploadChunk.overlap_short = chunkPolicy.overlap_short;
  uploadChunk.prefix_title = chunkPolicy.prefix_title;
  uploadChunk.prefix_section = chunkPolicy.prefix_section;
  uploadChunk.heading_aware = chunkPolicy.heading_aware;
}

function buildChunkFieldsPayload(source) {
  return {
    max_chars: source.max_chars,
    overlap: source.overlap,
    overlap_short: source.overlap_short,
    prefix_title: source.prefix_title,
    prefix_section: source.prefix_section,
    heading_aware: source.heading_aware,
  };
}

function applyChunkPolicyToDialog(data) {
  docChunkDialog.mode = data.use_project_default ? "project" : "custom";
  docChunkDialog.max_chars = data.max_chars;
  docChunkDialog.overlap = data.overlap;
  docChunkDialog.overlap_short = data.overlap_short;
  docChunkDialog.prefix_title = data.prefix_title;
  docChunkDialog.prefix_section = data.prefix_section;
  docChunkDialog.heading_aware = data.heading_aware;
  docChunkDialog.search_min_score = data.search_min_score ?? null;
}

async function openDocChunkDialog(doc) {
  docChunkDialog.open = true;
  docChunkDialog.docId = doc.id;
  docChunkDialog.title = doc.title;
  docChunkDialog.status = doc.status;
  docChunkDialog.err = "";
  try {
    const { data } = await client.get(
      `/api/knowledge/projects/${projectId.value}/documents/${doc.id}/chunk-policy`,
    );
    applyChunkPolicyToDialog(data);
  } catch (e) {
    docChunkDialog.err = formatApiError(e);
    syncUploadChunkFromProject();
    docChunkDialog.mode = doc.has_chunk_override ? "custom" : "project";
  }
}

async function saveDocChunkPolicy(reindex) {
  if (!docChunkDialog.docId) return;
  docChunkDialog.saving = true;
  docChunkDialog.err = "";
  try {
    const body = {
      use_project_default: docChunkDialog.mode === "project",
      ...(docChunkDialog.mode === "custom" ? buildChunkFieldsPayload(docChunkDialog) : {}),
    };
    await client.patch(
      `/api/knowledge/projects/${projectId.value}/documents/${docChunkDialog.docId}/chunk-policy`,
      body,
      { params: reindex ? { reindex: true } : {} },
    );
    docChunkDialog.open = false;
    msg.value = reindex ? "索引设置已保存，已排队重建索引" : "文档索引设置已保存";
    await refreshKnowledgeDocs();
  } catch (e) {
    docChunkDialog.err = formatApiError(e);
  } finally {
    docChunkDialog.saving = false;
  }
}

function resetSearchState() {
  searchQ.value = "";
  searchResults.value = [];
  searchDone.value = false;
  searching.value = false;
  lastSearchQuery.value = "";
  searchLatencyMs.value = null;
  searchMinScore.value = null;
}

function formatScore(score) {
  const n = Number(score);
  if (Number.isNaN(n)) return "";
  return n.toFixed(3);
}

function selectCollection(id) {
  selectedCollectionId.value = id;
  activeTab.value = "docs";
  resetSearchState();
  loadDocuments();
}

async function openCollectionDialog() {
  collDialog.open = true;
  collDialog.mode = "create";
  collDialog.id = null;
  collDialog.name = "";
  collDialog.description = "";
  collDialog.err = "";
  await nextTick();
  collNameInput.value?.focus();
}

async function openEditDialog() {
  if (!selectedCollection.value) return;
  collDialog.open = true;
  collDialog.mode = "edit";
  collDialog.id = selectedCollection.value.id;
  collDialog.name = selectedCollection.value.name;
  collDialog.description = selectedCollection.value.description || "";
  collDialog.err = "";
  await nextTick();
  collNameInput.value?.focus();
}

async function saveCollection() {
  collDialog.err = "";
  if (!collDialog.name.trim()) {
    collDialog.err = "请填写名称";
    return;
  }
  collSaving.value = true;
  try {
    if (collDialog.mode === "edit" && collDialog.id) {
      await client.patch(
        `/api/knowledge/projects/${projectId.value}/collections/${collDialog.id}`,
        {
          name: collDialog.name.trim(),
          description: collDialog.description,
        },
      );
      collDialog.open = false;
      await loadCollections();
      selectedCollectionId.value = collDialog.id;
      msg.value = "集合已更新";
      return;
    }
    const { data } = await client.post(`/api/knowledge/projects/${projectId.value}/collections`, {
      name: collDialog.name.trim(),
      description: collDialog.description,
    });
    collDialog.open = false;
    await loadCollections();
    selectedCollectionId.value = data.id;
    activeTab.value = "add";
    addMode.value = "upload";
    msg.value = "集合已创建，可开始上传文档";
    await refreshKnowledgeDocs();
  } catch (e) {
    collDialog.err = formatApiError(e);
  } finally {
    collSaving.value = false;
  }
}

function openDeleteDialog() {
  if (!selectedCollection.value) return;
  deleteDialog.open = true;
  deleteDialog.id = selectedCollection.value.id;
  deleteDialog.name = selectedCollection.value.name;
  deleteDialog.docCount = documents.value.length;
  deleteDialog.err = "";
}

async function confirmDeleteCollection() {
  if (!deleteDialog.id) return;
  deletingCollection.value = true;
  deleteDialog.err = "";
  error.value = "";
  try {
    await client.delete(
      `/api/knowledge/projects/${projectId.value}/collections/${deleteDialog.id}`,
    );
    deleteDialog.open = false;
    selectedCollectionId.value = null;
    documents.value = [];
    msg.value = "知识集合已删除";
    await loadCollections();
    if (collections.value.length) {
      selectedCollectionId.value = collections.value[0].id;
      await refreshKnowledgeDocs();
    }
  } catch (e) {
    deleteDialog.err = formatApiError(e);
  } finally {
    deletingCollection.value = false;
  }
}

function onFileChange(ev) {
  const file = ev.target.files?.[0] || null;
  if (file && !isAllowedUploadFile(file)) {
    error.value = "不支持的文件类型，请参见下方支持格式说明";
    ev.target.value = "";
    upload.file = null;
    return;
  }
  if (file && !validateUploadFileSize(file)) {
    error.value = `文件过大，单文件上限 ${MAX_UPLOAD_BYTES / (1024 * 1024)}MB`;
    ev.target.value = "";
    upload.file = null;
    return;
  }
  upload.file = file;
  error.value = "";
}

function onFileDrop(ev) {
  uploadDragOver.value = false;
  const file = ev.dataTransfer?.files?.[0] || null;
  if (!file) return;
  if (!isAllowedUploadFile(file)) {
    error.value = "不支持的文件类型，请参见下方支持格式说明";
    return;
  }
  if (!validateUploadFileSize(file)) {
    error.value = `文件过大，单文件上限 ${MAX_UPLOAD_BYTES / (1024 * 1024)}MB`;
    return;
  }
  upload.file = file;
  error.value = "";
}

function triggerFileSelect() {
  fileInputRef.value?.click();
}

function clearUploadFile() {
  upload.file = null;
  if (fileInputRef.value) fileInputRef.value.value = "";
}

function fileExtLabel(name) {
  const ext = (name.split(".").pop() || "").toUpperCase();
  return ext || "FILE";
}

function fileIconClass(name) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  if (ext === "pdf") return "file-icon--pdf";
  if (ext === "docx") return "file-icon--doc";
  if (ext === "json") return "file-icon--json";
  if (ext === "xlsx" || ext === "xls") return "file-icon--sheet";
  if (ext === "html" || ext === "htm") return "file-icon--html";
  if (ext === "csv") return "file-icon--csv";
  return "file-icon--text";
}

function formatFileSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

async function submitUpload() {
  if (!selectedCollectionId.value || !upload.file) return;
  uploading.value = true;
  msg.value = "";
  error.value = "";
  try {
    const fd = new FormData();
    fd.append("collection_id", String(selectedCollectionId.value));
    fd.append("doc_type", upload.doc_type);
    fd.append("title", upload.title);
    fd.append("use_project_chunk_policy", uploadChunkMode.value === "project" ? "true" : "false");
    if (uploadChunkMode.value === "custom") {
      fd.append("chunk_policy_json", JSON.stringify(buildChunkFieldsPayload(uploadChunk)));
    }
    fd.append("file", upload.file);
    await client.post(`/api/knowledge/projects/${projectId.value}/documents/upload`, fd);
    msg.value = "已上传，后台正在索引";
    clearUploadFile();
    upload.title = "";
    activeTab.value = "docs";
    await refreshKnowledgeDocs();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    uploading.value = false;
  }
}

async function submitStructured() {
  if (!selectedCollectionId.value) return;
  structSaving.value = true;
  error.value = "";
  try {
    const structured_json = JSON.parse(structured.jsonText || "{}");
    await client.post(`/api/knowledge/projects/${projectId.value}/documents/structured`, {
      collection_id: selectedCollectionId.value,
      doc_type: structured.doc_type,
      title: structured.title.trim() || "结构化文档",
      structured_json,
    });
    msg.value = "结构化文档已保存";
    activeTab.value = "docs";
    await refreshKnowledgeDocs();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    structSaving.value = false;
  }
}

async function submitDocReview(docId) {
  try {
    await client.post(`/api/knowledge/projects/${projectId.value}/documents/${docId}/submit-review`);
    msg.value = "已提交审核";
    await refreshKnowledgeDocs();
  } catch (e) {
    error.value = formatApiError(e);
  }
}

async function reindexDoc(docId) {
  try {
    await client.post(`/api/knowledge/documents/${docId}/reindex`);
    msg.value = "已排队重建索引";
  } catch (e) {
    error.value = formatApiError(e);
  }
}

function openDeleteDocDialog(doc) {
  deleteDocDialog.open = true;
  deleteDocDialog.id = doc.id;
  deleteDocDialog.title = doc.title;
  deleteDocDialog.err = "";
}

async function confirmDeleteDocument() {
  if (!deleteDocDialog.id) return;
  deletingDoc.value = true;
  deleteDocDialog.err = "";
  error.value = "";
  try {
    await client.delete(
      `/api/knowledge/projects/${projectId.value}/documents/${deleteDocDialog.id}`,
    );
    deleteDocDialog.open = false;
    msg.value = "文档及索引已删除";
    await refreshKnowledgeDocs();
  } catch (e) {
    deleteDocDialog.err = formatApiError(e);
  } finally {
    deletingDoc.value = false;
  }
}

async function runSearch() {
  const q = searchQ.value.trim();
  if (!q) return;
  searching.value = true;
  searchDone.value = false;
  searchResults.value = [];
  lastSearchQuery.value = q;
  searchLatencyMs.value = null;
  searchMinScore.value = null;
  error.value = "";
  try {
    const params = { q, limit: 10 };
    if (selectedCollectionId.value) params.collection_id = selectedCollectionId.value;
    const { data } = await client.get(`/api/knowledge/projects/${projectId.value}/search`, { params });
    searchResults.value = data.items || [];
    searchLatencyMs.value = data.latency_ms ?? null;
    searchMinScore.value = data.min_score ?? null;
    if (data.error) {
      error.value = String(data.error);
    }
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    searching.value = false;
    searchDone.value = true;
  }
}

async function bootstrap() {
  loading.value = true;
  error.value = "";
  resetSearchState();
  try {
    await loadProject();
    await loadCollections();
    await loadChunkPolicy();
    await loadDocuments();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

watch(activeTab, (tab, prev) => {
  if (prev === "search" && tab !== "search") {
    resetSearchState();
  }
});

watch(projectId, bootstrap);
onMounted(bootstrap);
</script>

<style scoped>
.kb-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}
.sub {
  color: var(--muted, #666);
  margin: 0.25rem 0 0;
}
.card {
  background: #fff;
  border: 1px solid #e8edf3;
  border-radius: 10px;
}
.kb-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1rem;
  align-items: start;
}
.kb-sidebar {
  padding: 0.85rem;
  position: sticky;
  top: 1rem;
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.sidebar-head h2 {
  margin: 0;
  font-size: 0.95rem;
}
.coll-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.coll-item {
  width: 100%;
  text-align: left;
  padding: 0.65rem 0.75rem;
  border: 1px solid transparent;
  border-radius: 8px;
  background: #f8fafc;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s;
}
.coll-item:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
}
.coll-item.active {
  background: #eff6ff;
  border-color: #3b82f6;
  box-shadow: inset 3px 0 0 #3b82f6;
}
.coll-name {
  display: block;
  font-weight: 600;
  font-size: 0.9rem;
  color: #0f172a;
}
.coll-desc {
  display: block;
  margin-top: 0.2rem;
  font-size: 0.78rem;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sidebar-empty {
  text-align: center;
  padding: 1.25rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  align-items: center;
}
.sidebar-settings {
  margin-top: 1rem;
  padding-top: 0.85rem;
  border-top: 1px solid #e8edf3;
}
.sidebar-settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  margin-bottom: 0.35rem;
}
.sidebar-settings-head h3 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #0f172a;
}
.settings-badge {
  font-size: 0.62rem;
  padding: 0.1rem 0.35rem;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
}
.settings-hint {
  margin: 0 0 0.65rem;
  line-height: 1.4;
}
.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.45rem;
  margin-bottom: 0.55rem;
}
.settings-field {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.72rem;
  color: #64748b;
}
.settings-field input {
  height: 26px;
  padding: 0 0.4rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font: inherit;
  font-size: 0.75rem;
  box-sizing: border-box;
}
.settings-checks {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.65rem;
}
.settings-check {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  color: #475569;
  cursor: pointer;
}
.settings-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}
.kb-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.main-empty {
  padding: 3rem 2rem;
  text-align: center;
}
.empty-icon {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}
.main-empty h3 {
  margin: 0 0 0.35rem;
}
.main-head {
  padding: 0.85rem 1.1rem;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.main-head h2 {
  margin: 0;
  font-size: 1.05rem;
}
.main-head-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.coll-doc-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.45rem;
}
.main-head-actions {
  display: flex;
  flex-shrink: 0;
  gap: 0.35rem;
}

/* —— 统一按钮体系 —— */
.kb-link-btn {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  text-decoration: none;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.kb-link-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
  text-decoration: none;
}

.kb-toolbar-btn,
.kb-btn,
.kb-action-btn,
.kb-modal-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  font-family: inherit;
  font-weight: 500;
  line-height: 1.2;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.kb-toolbar-btn:disabled,
.kb-btn:disabled,
.kb-action-btn:disabled,
.kb-modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 工具栏：新建 / 编辑 / 删除 / 添加文档 */
.kb-toolbar-btn {
  height: 26px;
  padding: 0 10px;
  font-size: 0.75rem;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
}
.kb-toolbar-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
}
.kb-toolbar-btn--primary {
  color: #2563eb;
  border-color: #bfdbfe;
  background: #f8fbff;
}
.kb-toolbar-btn--primary:hover:not(:disabled) {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1d4ed8;
}
.kb-toolbar-btn--danger {
  color: #dc2626;
  border-color: #fecaca;
}
.kb-toolbar-btn--danger:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #b91c1c;
}

/* 表单主操作 */
.kb-btn {
  height: 30px;
  padding: 0 14px;
  font-size: 0.8125rem;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
}
.kb-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #cbd5e1;
}
.kb-btn--primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
  box-shadow: none;
}
.kb-btn--primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

/* 文档行内操作 */
.kb-action-btn {
  height: 24px;
  padding: 0 8px;
  font-size: 0.72rem;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
}
.kb-action-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
}
.kb-action-btn--danger {
  color: #dc2626;
  border-color: #fecaca;
}
.kb-action-btn--danger:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #b91c1c;
}

.tab-bar {
  display: flex;
  padding: 0.35rem;
  gap: 0.25rem;
}
.tab {
  flex: 1;
  padding: 0.45rem 0.65rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  font-size: 0.8125rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  transition: background 0.12s, color 0.12s;
}
.tab:hover {
  background: #f1f5f9;
  color: #334155;
}
.tab.active {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
.tab-badge {
  font-size: 0.75rem;
  background: #dbeafe;
  color: #1d4ed8;
  padding: 0.05rem 0.4rem;
  border-radius: 999px;
}
.card.block {
  padding: 1rem 1.25rem;
}
.add-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid #e8edf3;
  padding-bottom: 0.65rem;
}
.add-tab {
  padding: 0.28rem 0.65rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  font-size: 0.78rem;
  cursor: pointer;
}
.add-tab.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
.add-panel {
  padding-top: 0.25rem;
}
.upload-section-title {
  margin: 0 0 1rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #0f172a;
}
.upload-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.upload-option {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.upload-option span {
  font-size: 0.82rem;
  color: #64748b;
}
.upload-option select,
.upload-option input {
  height: 32px;
  padding: 0 0.65rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font: inherit;
  font-size: 0.8125rem;
  box-sizing: border-box;
}
.upload-dropzone {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.upload-dropzone:hover,
.upload-dropzone--active {
  border-color: #93c5fd;
  background: #eff6ff;
}
.upload-dropzone--has-file {
  cursor: default;
  background: #fff;
  border-style: solid;
  border-color: #e2e8f0;
  padding: 0.75rem;
  min-height: auto;
}
.upload-input-hidden {
  display: none;
}
.dropzone-empty {
  text-align: center;
  padding: 1.5rem 1rem;
  pointer-events: none;
}
.dropzone-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
  opacity: 0.85;
}
.dropzone-text {
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
  color: #334155;
}
.dropzone-link {
  border: none;
  background: none;
  color: #2563eb;
  font: inherit;
  font-size: 0.875rem;
  cursor: pointer;
  padding: 0;
  pointer-events: auto;
}
.dropzone-link:hover {
  text-decoration: underline;
}
.dropzone-hint {
  margin: 0;
  font-size: 0.75rem;
  color: #94a3b8;
  line-height: 1.45;
  max-width: 420px;
}
.dropzone-file {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.65rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}
.file-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 700;
  color: #fff;
}
.file-icon--pdf {
  background: #ef4444;
}
.file-icon--doc {
  background: #2563eb;
}
.file-icon--json {
  background: #8b5cf6;
}
.file-icon--text {
  background: #64748b;
}
.file-icon--sheet {
  background: #059669;
}
.file-icon--html {
  background: #ea580c;
}
.file-icon--csv {
  background: #0891b2;
}
.file-info {
  flex: 1;
  min-width: 0;
}
.file-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-meta {
  margin-top: 0.15rem;
  font-size: 0.75rem;
  color: #94a3b8;
}
.file-remove {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
  opacity: 0.55;
  transition: opacity 0.12s, background 0.12s;
}
.file-remove:hover {
  opacity: 1;
  background: #fef2f2;
}
.upload-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid #f1f5f9;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}
.field.full {
  grid-column: 1 / -1;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.field span {
  font-size: 0.85rem;
  color: #475569;
}
.doc-hint {
  line-height: 1.55;
  padding: 0.65rem 0.75rem;
  background: #f8fafc;
  border-radius: 8px;
  border-left: 3px solid #3b82f6;
  margin-bottom: 0.85rem;
}
.filter-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.85rem;
}
.filter-label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.82rem;
  color: #64748b;
}
.filter-label select {
  min-width: 160px;
  height: 26px;
  padding: 0 0.55rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.8125rem;
  box-sizing: border-box;
}
.doc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.doc-item {
  display: grid;
  grid-template-columns: 1fr 7.5rem;
  column-gap: 1rem;
  align-items: end;
  padding: 0.85rem 1rem;
  background: linear-gradient(180deg, #fafbfc 0%, #fff 100%);
  border: 1px solid #e8edf3;
  border-radius: 10px;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}
.doc-main {
  min-width: 0;
}
.doc-item:hover {
  border-color: #c7d7fe;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.08);
}
.doc-title {
  font-weight: 600;
  font-size: 0.98rem;
  color: #0f172a;
  margin-bottom: 0.4rem;
  line-height: 1.35;
}
.doc-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
}
.type-tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 0.5rem;
  font-size: 0.72rem;
  border-radius: 4px;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  box-sizing: border-box;
}
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  height: 24px;
  padding: 0 0.5rem;
  font-size: 0.72rem;
  font-weight: 500;
  border-radius: 999px;
  box-sizing: border-box;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: currentColor;
}
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  height: 24px;
  padding: 0 0.55rem;
  font-size: 0.72rem;
  font-weight: 500;
  border-radius: 999px;
  box-sizing: border-box;
}
.status-chip--mini {
  height: 18px;
  padding: 0 0.35rem;
  font-size: 0.65rem;
}
.status-chip--mini .status-dot {
  width: 6px;
  height: 6px;
}
.status-chip-count {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.doc-time {
  display: inline-flex;
  align-items: center;
  height: 24px;
  font-size: 0.72rem;
}
.status--draft,
.status--default {
  background: #f1f5f9;
  color: #475569;
}
.status--pending {
  background: #f8fafc;
  color: #64748b;
  border: 1px dashed #cbd5e1;
}
.status--parsing {
  background: #eff6ff;
  color: #1d4ed8;
  animation: pulse-soft 1.5s ease-in-out infinite;
}
.status--review {
  background: #fffbeb;
  color: #b45309;
  border: 1px solid #fde68a;
}
.status--active {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
}
.status--rejected {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}
.status--archived {
  background: #f4f4f5;
  color: #71717a;
}
@keyframes pulse-soft {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.65;
  }
}
.doc-actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-end;
  gap: 0.3rem;
  width: 7.5rem;
}
.custom-index-tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 0.45rem;
  font-size: 0.68rem;
  font-weight: 500;
  border-radius: 4px;
  background: #f5f3ff;
  color: #6d28d9;
  border: 1px solid #ddd6fe;
  box-sizing: border-box;
}
.upload-advanced {
  margin-top: 0.85rem;
  border-top: 1px solid #f1f5f9;
  padding-top: 0.65rem;
}
.upload-advanced-toggle {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 500;
  color: #475569;
  cursor: pointer;
}
.upload-advanced-toggle:hover {
  color: #1d4ed8;
}
.upload-advanced-panel {
  margin-top: 0.65rem;
  padding: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e8edf3;
  border-radius: 8px;
}
.chunk-mode-option {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  font-size: 0.82rem;
  color: #334155;
  margin-bottom: 0.45rem;
  cursor: pointer;
}
.chunk-fields {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px dashed #e2e8f0;
}
.doc-actions .kb-action-btn {
  width: 100%;
  box-sizing: border-box;
}
.reindex-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0.15rem 0.35rem;
  font-size: 0.65rem;
  line-height: 1.25;
  color: #94a3b8;
  text-align: center;
  border-radius: 4px;
  background: #f8fafc;
  border: 1px dashed #e2e8f0;
  box-sizing: border-box;
}
.empty-doc {
  text-align: center;
  padding: 2rem 1rem;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px dashed #e2e8f0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.65rem;
}
.search-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.search-row input {
  flex: 1;
  height: 34px;
  padding: 0 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font: inherit;
}
.search-row .kb-btn {
  flex-shrink: 0;
  height: 34px;
}
.search-meta {
  margin: 0 0 0.75rem;
}
.hit-score {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #64748b;
}
.hint.warn {
  color: #b45309;
  background: #fffbeb;
  padding: 0.5rem 0.65rem;
  border-radius: 6px;
}
.hit {
  border-top: 1px solid #eee;
  padding: 0.65rem 0;
}
.hit h4 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}
.hit p {
  margin: 0;
  color: #444;
  font-size: 0.88rem;
  white-space: pre-wrap;
}
.banner {
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  margin-bottom: 0.75rem;
}
.banner.err {
  background: #fdecea;
  color: #b42318;
}
.banner.ok {
  background: #e8f5e9;
  color: #1b5e20;
}
.err {
  color: #b91c1c;
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .kb-layout {
    grid-template-columns: 1fr;
  }
  .kb-sidebar {
    position: static;
  }
  .coll-list {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .coll-item {
    width: auto;
    flex: 1 1 auto;
    min-width: 120px;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
  .upload-options {
    grid-template-columns: 1fr;
  }
  .doc-item {
    grid-template-columns: 1fr;
    row-gap: 0.65rem;
  }
  .doc-actions {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .doc-actions .kb-action-btn {
    width: auto;
  }
  .reindex-hint {
    width: auto;
    max-width: none;
  }
}
</style>

<!-- Teleport 到 body，需独立类名 -->
<style>
.kb-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 1000;
}
.kb-modal {
  width: 100%;
  max-width: 440px;
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
  border: 1px solid #e2e8f0;
}
.kb-modal-wide {
  max-width: 520px;
}
.kb-modal h3 {
  margin: 0 0 0.35rem;
}
.kb-modal .modal-desc {
  margin: 0 0 1rem;
}
.kb-modal .field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}
.kb-modal .field span {
  font-size: 0.85rem;
  color: #475569;
}
.kb-modal input,
.kb-modal textarea {
  padding: 0.55rem 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
}
.kb-modal .modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
.kb-modal-btn {
  height: 30px;
  padding: 0 14px;
  font-size: 0.8125rem;
  font-weight: 500;
  font-family: inherit;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.kb-modal-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #cbd5e1;
}
.kb-modal-btn--primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.kb-modal-btn--primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}
.kb-modal-btn--danger {
  background: #dc2626;
  border-color: #dc2626;
  color: #fff;
}
.kb-modal-btn--danger:hover:not(:disabled) {
  background: #b91c1c;
  border-color: #b91c1c;
}
.kb-modal-danger .warn-box {
  background: #fffbeb;
  color: #b45309;
  padding: 0.55rem 0.65rem;
  border-radius: 6px;
  margin: 0 0 0.75rem;
  line-height: 1.45;
}
</style>
