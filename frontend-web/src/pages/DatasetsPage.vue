<script setup lang="ts">
import { computed, ref } from "vue";
import AppShell from "../components/AppShell.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { authFetch } from "../lib/auth";
import type { AuthApiResponse, DatasetSummary, MysqlRegisterResult, UploadDatasetResult } from "../lib/types";
import { datasetTypeLabel, workspaceStore } from "../lib/workspace-store";

// mock 数据是非响应式的静态数组，新上传的数据集放在这里才能触发视图更新
const uploadedDatasets = ref<DatasetSummary[]>([]);
const allDatasets = computed(() => [...uploadedDatasets.value, ...workspaceStore.datasets]);

const ALLOWED_EXTENSIONS = ["csv", "xlsx","xls"];
const MAX_FILE_SIZE = 20 * 1024 * 1024;

const selectedFile = ref<File | null>(null);
const datasetName = ref("");
const description = ref("");
const uploading = ref(false);
const successMessage = ref("");
const errorMessage = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  errorMessage.value = "";
  successMessage.value = "";

  if (!file) {
    selectedFile.value = null;
    return;
  }

  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    selectedFile.value = null;
    input.value = "";
    errorMessage.value = "文件格式不支持，仅支持 .csv / .xlsx / .xls";
    return;
  }

  if (file.size > MAX_FILE_SIZE) {
    selectedFile.value = null;
    input.value = "";
    errorMessage.value = "文件大小不能超过 20MB";
    return;
  }

  selectedFile.value = file;
  if (!datasetName.value.trim()) {
    datasetName.value = file.name.replace(/\.[^.]+$/, "");
  }
}

async function handleUpload() {
  successMessage.value = "";
  errorMessage.value = "";

  if (!selectedFile.value) {
    errorMessage.value = "请先选择要上传的文件";
    return;
  }
  if (!datasetName.value.trim()) {
    errorMessage.value = "请填写数据集名称";
    return;
  }

  const form = new FormData();
  form.append("file", selectedFile.value);
  form.append("datasetName", datasetName.value.trim());
  if (description.value.trim()) {
    form.append("description", description.value.trim());
  }

  uploading.value = true;
  try {
    const response = await authFetch("/api/datasets/upload", {
      method: "POST",
      body: form,
    });
    const payload = (await response.json().catch(() => null)) as AuthApiResponse<UploadDatasetResult> | null;

    if (response.ok && payload?.success && payload.data) {
      successMessage.value = `上传成功：数据集 ${payload.data.datasetId}（${payload.data.sourceType}）已注册，当前状态 ${payload.data.status}`;
      uploadedDatasets.value.unshift({
        id: payload.data.datasetId,
        datasetName: datasetName.value.trim(),
        description: description.value.trim() || "（暂无描述）",
        datasetType: ["XLSX", "XLS"].includes(payload.data.sourceType) ? "excel" : "csv",
        sourceLocation: `oss://tlias-chao/datasets/${payload.data.datasetId}`,
        permissionScope: "当前用户",
        owner: "我",
        tenantId: "tenant-demo",
        createdAt: new Date().toISOString().slice(0, 10),
        rowCount: 0,
        schemaSummary: ["待解析"],
        sampleRows: [],
      });
      selectedFile.value = null;
      datasetName.value = "";
      description.value = "";
      if (fileInput.value) {
        fileInput.value.value = "";
      }
    } else {
      errorMessage.value = payload?.message || `上传失败（HTTP ${response.status}），请稍后再试。`;
    }
  } catch {
    errorMessage.value = "网络异常，无法连接上传服务，请稍后再试。";
  } finally {
    uploading.value = false;
  }
}

const mysqlForm = ref({
  datasetName: "",
  host: "",
  port: "3306",
  database: "",
  username: "",
  password: "",
  tableNames: "",
});
const mysqlRegistering = ref(false);
const mysqlSuccessMessage = ref("");
const mysqlErrorMessage = ref("");

function validateMysqlForm(): string | null {
  if (!mysqlForm.value.datasetName.trim()) return "数据集名称不能为空";
  if (!mysqlForm.value.host.trim()) return "主机地址不能为空";
  const port = Number(mysqlForm.value.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return "端口必须是 1-65535 之间的整数";
  if (!mysqlForm.value.database.trim()) return "数据库名称不能为空";
  if (!mysqlForm.value.username.trim()) return "用户名不能为空";
  if (!mysqlForm.value.password) return "密码不能为空";
  if (!mysqlForm.value.tableNames.trim()) return "表名至少填写一个";
  return null;
}

function parseTableNames(): string[] {
  return mysqlForm.value.tableNames
    .split(/[,，;；\s]+/)
    .map((name) => name.trim())
    .filter(Boolean);
}

async function handleMysqlRegister() {
  mysqlSuccessMessage.value = "";
  mysqlErrorMessage.value = "";

  const validationError = validateMysqlForm();
  if (validationError) {
    mysqlErrorMessage.value = validationError;
    return;
  }

  const tableNames = parseTableNames();
  const payloadBody = {
    datasetName: mysqlForm.value.datasetName.trim(),
    host: mysqlForm.value.host.trim(),
    port: Number(mysqlForm.value.port),
    database: mysqlForm.value.database.trim(),
    username: mysqlForm.value.username.trim(),
    password: mysqlForm.value.password,
    tableNames,
  };

  mysqlRegistering.value = true;
  try {
    const response = await authFetch("/api/datasets/mysql/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadBody),
    });
    const payload = (await response.json().catch(() => null)) as AuthApiResponse<MysqlRegisterResult> | null;

    if (response.ok && payload?.success && payload.data) {
      mysqlSuccessMessage.value = `注册成功：数据集 ${payload.data.datasetId} 已连接 ${payload.data.tableNames.join("、")}，状态 ${payload.data.status}`;
      uploadedDatasets.value.unshift({
        id: payload.data.datasetId,
        datasetName: payloadBody.datasetName,
        description: `MySQL 数据源 ${payloadBody.host}:${payloadBody.port}/${payloadBody.database}`,
        datasetType: "mysql",
        sourceLocation: `mysql://${payloadBody.host}:${payloadBody.port}/${payloadBody.database}`,
        permissionScope: "只读",
        owner: "我",
        tenantId: "tenant-demo",
        createdAt: new Date().toISOString().slice(0, 10),
        rowCount: 0,
        schemaSummary: payload.data.tableNames.map((table) => `表: ${table}`),
        sampleRows: [],
      });
      mysqlForm.value = {
        datasetName: "",
        host: "",
        port: "3306",
        database: "",
        username: "",
        password: "",
        tableNames: "",
      };
    } else {
      mysqlErrorMessage.value = payload?.message || `注册失败（HTTP ${response.status}），请稍后再试。`;
    }
  } catch {
    mysqlErrorMessage.value = "网络异常，无法连接注册服务，请稍后再试。";
  } finally {
    mysqlRegistering.value = false;
  }
}
</script>

<template>
  <AppShell>
    <div class="space-y-6 pb-8">
      <SectionCard title="数据集管理" description="统一管理 CSV / Excel / MySQL 数据集，展示 Schema 摘要、样例预览、权限范围与接入状态。">
        <template #action>
          <StatusBadge :label="`${allDatasets.length} 个数据集`" tone="default" />
        </template>

        <div class="grid gap-4 xl:grid-cols-2">
          <div v-for="dataset in allDatasets" :key="dataset.id" class="rounded-[24px] border border-slate-200 bg-slate-50/70 p-5">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="text-base font-semibold text-slate-900">{{ dataset.datasetName }}</div>
                <p class="mt-2 text-sm leading-7 text-slate-500">{{ dataset.description }}</p>
              </div>
              <div class="flex flex-wrap gap-2">
                <StatusBadge :label="datasetTypeLabel[dataset.datasetType]" tone="default" />
                <StatusBadge label="已授权" tone="succeeded" />
              </div>
            </div>

            <div class="mt-4 grid gap-3 sm:grid-cols-2">
              <div v-for="item in [
                ['source_location', dataset.sourceLocation],
                ['permission_scope', dataset.permissionScope],
                ['owner', dataset.owner],
                ['tenant_id', dataset.tenantId],
                ['created_at', dataset.createdAt],
                ['row_count', `${dataset.rowCount}`],
              ]" :key="item[0]" class="rounded-[18px] border border-slate-200 bg-white px-4 py-3">
                <div class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{{ item[0] }}</div>
                <div class="mt-2 text-sm text-slate-700">{{ item[1] }}</div>
              </div>
            </div>

            <div class="mt-4 flex flex-wrap gap-2">
              <span v-for="field in dataset.schemaSummary" :key="field" class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-500">
                {{ field }}
              </span>
            </div>

            <div class="mt-4 rounded-[20px] border border-slate-200 bg-white p-4">
              <div class="flex items-center justify-between gap-3">
                <div class="text-sm font-semibold text-slate-900">样例数据预览</div>
                <button class="text-xs font-semibold text-teal-700">查看完整样例</button>
              </div>
              <div class="mt-3 space-y-2 text-sm text-slate-600">
                <div v-for="(row, index) in dataset.sampleRows.slice(0, 2)" :key="index" class="rounded-2xl bg-slate-50 px-3 py-2">
                  {{ Object.entries(row).map(([key, value]) => `${key}: ${value}`).join(" / ") }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </SectionCard>

      <div class="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <SectionCard title="上传 CSV / Excel" description="保留文件上传注册入口，强调名称、描述、格式提示、成功反馈与失败校验。">
          <template #action>
            <StatusBadge label="文件数据集" tone="default" />
          </template>

          <div class="rounded-[24px] border border-dashed border-teal-200 bg-teal-50/50 p-6">
            <div class="text-base font-semibold text-slate-900">拖拽或点击选择文件</div>
            <p class="mt-2 text-sm leading-7 text-slate-500">
              支持 CSV / Excel。上传成功后自动生成 Schema 摘要与样例预览，并进入已授权数据集列表。
            </p>

            <label class="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-teal-300 bg-white px-4 py-6 text-center transition hover:border-teal-500 hover:bg-teal-50">
              <input ref="fileInput" type="file" accept=".csv,.xlsx,.xls" class="hidden" @change="onFileChange" />
              <span class="text-sm font-medium text-teal-700">{{ selectedFile ? selectedFile.name : "点击选择 .csv / .xlsx / .xls 文件" }}</span>
              <span v-if="selectedFile" class="mt-1 text-xs text-slate-400">{{ (selectedFile.size / 1024).toFixed(1) }} KB</span>
            </label>

            <div class="mt-5 grid gap-4">
              <label class="block">
                <span class="text-sm font-medium text-slate-700">数据集名称</span>
                <input v-model="datasetName" placeholder="例如：school_exam_summary_2026" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
              </label>
              <label class="block">
                <span class="text-sm font-medium text-slate-700">描述信息</span>
                <input v-model="description" placeholder="简要描述数据用途，便于后续分析" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
              </label>
            </div>

            <div class="mt-5 grid gap-3 sm:grid-cols-2">
              <button type="button" class="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700" @click="fileInput?.click()">选择文件</button>
              <button type="button" :disabled="uploading" class="rounded-2xl bg-teal-600 px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60" @click="handleUpload">
                {{ uploading ? "上传中…" : "上传并注册" }}
              </button>
            </div>

            <div v-if="successMessage" class="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {{ successMessage }}
            </div>
            <div v-if="errorMessage" class="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {{ errorMessage }}
            </div>
          </div>
        </SectionCard>

        <SectionCard title="注册 MySQL 只读数据集" description="填写连接信息与表名，系统将测试连通性、读取表结构并加密保存凭据。">
          <template #action>
            <StatusBadge label="Read Only" tone="needs_review" />
          </template>

          <div class="grid gap-4 sm:grid-cols-2">
            <label class="block sm:col-span-2">
              <span class="text-sm font-medium text-slate-700">数据集名称</span>
              <input v-model="mysqlForm.datasetName" placeholder="例如：sales_mysql" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
            </label>
            <label class="block">
              <span class="text-sm font-medium text-slate-700">主机</span>
              <input v-model="mysqlForm.host" placeholder="例如：127.0.0.1" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
            </label>
            <label class="block">
              <span class="text-sm font-medium text-slate-700">端口</span>
              <input v-model="mysqlForm.port" placeholder="3306" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
            </label>
            <label class="block">
              <span class="text-sm font-medium text-slate-700">数据库名</span>
              <input v-model="mysqlForm.database" placeholder="例如：demo" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
            </label>
            <label class="block">
              <span class="text-sm font-medium text-slate-700">用户名</span>
              <input v-model="mysqlForm.username" placeholder="建议使用只读账号" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
            </label>
            <label class="block sm:col-span-2">
              <span class="text-sm font-medium text-slate-700">密码</span>
              <input v-model="mysqlForm.password" type="password" placeholder="连接密码（加密存储，不会回显）" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
            </label>
            <label class="block sm:col-span-2">
              <span class="text-sm font-medium text-slate-700">表名</span>
              <input v-model="mysqlForm.tableNames" placeholder="多个表用逗号分隔，例如：sales, region_snapshot" class="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none" />
            </label>
          </div>
          <div class="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-800">
            只读属性提示：系统仅接收只读凭据，后续分析仅允许生成和执行 SELECT 查询。
          </div>
          <div class="mt-5">
            <button type="button" :disabled="mysqlRegistering" class="w-full rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60" @click="handleMysqlRegister">
              {{ mysqlRegistering ? "正在连接并读取表结构…" : "注册数据集" }}
            </button>
          </div>

          <div v-if="mysqlSuccessMessage" class="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {{ mysqlSuccessMessage }}
          </div>
          <div v-if="mysqlErrorMessage" class="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {{ mysqlErrorMessage }}
          </div>
        </SectionCard>
      </div>
    </div>
  </AppShell>
</template>
