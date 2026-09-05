<!-- @ai-generated -->
<!--
  商品新增/编辑页
  路由：
  - /goods/edit            新增
  - /goods/edit/:goodsId?source_channel=xxx  编辑
  布局：顶部主图+基本信息并排，底部分价格/状态两栏（与详情页一致）
-->
<template>
  <div class="goods-edit-page">
    <el-page-header @back="$router.push('/goods/list')" class="page-header">
      <template #content>
        <span class="page-title">{{ isEdit ? '编辑商品' : '新增商品' }}</span>
      </template>
    </el-page-header>

    <div v-loading="loading">
      <!-- 顶部：主图 + 基本信息（并排） -->
      <el-card shadow="never" class="section-card">
        <div class="edit-top-area">
          <!-- 左：主图上传 -->
          <div class="edit-image-wrap">
            <el-image
              v-if="form.goods_img"
              :src="form.goods_img"
              :preview-src-list="[form.goods_img]"
              preview-teleported
              fit="contain"
              class="edit-main-img"
            />
            <div v-else class="no-image">暂无主图</div>
            <el-button class="upload-btn" @click="openUpload">
              <el-icon><Upload /></el-icon>上传主图
            </el-button>
          </div>

          <!-- 右：基本信息表单 -->
          <div class="edit-basic-wrap">
            <el-form
              ref="formRef"
              :model="form"
              :rules="rules"
              label-width="100px"
              @submit.prevent
            >
              <el-form-item label="商品标题" prop="goods_title">
                <el-input v-model="form.goods_title" placeholder="商品标题" maxlength="512" show-word-limit />
              </el-form-item>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="来源渠道" prop="source_channel">
                    <el-select v-model="form.source_channel" placeholder="请选择渠道" :disabled="isEdit" style="width: 100%">
                      <el-option label="喵有券 (myq)" value="myq" />
                      <el-option label="订单侠 (orderx)" value="orderx" />
                      <el-option label="大淘客 (dta)" value="dta" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="商品ID" prop="goods_id">
                    <el-input
                      v-model="form.goods_id"
                      placeholder="CPS 渠道商品唯一ID"
                      maxlength="128"
                      :disabled="isEdit"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="商品类目" prop="category">
                    <el-input v-model="form.category" placeholder="商品类目" maxlength="64" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="店铺名称" prop="shop_name">
                    <el-input v-model="form.shop_name" placeholder="店铺名称" maxlength="128" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="主图URL" prop="goods_img">
                <el-input v-model="form.goods_img" placeholder="图片URL，或点击左侧上传按钮" maxlength="1024" />
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-card>

      <!-- 底部：价格 + 状态（两栏并排） -->
      <el-row :gutter="12">
        <!-- 左：价格 -->
        <el-col :span="12">
          <el-card shadow="never" class="section-card">
            <template #header><span class="card-title">价格</span></template>
            <el-form :model="form" label-width="120px" @submit.prevent>
              <el-form-item label="商品原价(元)">
                <el-input-number v-model="form.original_price" :min="0" :precision="2" :step="1" controls-position="right" />
              </el-form-item>
              <el-form-item label="销售价(元)" prop="sale_price">
                <el-input-number v-model="form.sale_price" :min="0" :precision="2" :step="1" controls-position="right" />
              </el-form-item>
              <el-form-item label="佣金比例(%)" prop="commission_rate">
                <el-input-number v-model="form.commission_rate" :min="0" :max="100" :precision="2" :step="1" controls-position="right" />
              </el-form-item>
              <el-form-item label="普通会员奖金">
                <div class="bonus-row">
                  <el-input-number v-model="form.bonus_price_normal" :min="0" :precision="2" :step="1" controls-position="right" placeholder="奖金(元)" />
                  <span class="bonus-sep">/</span>
                  <el-input-number v-model="form.bonus_rate_normal" :min="0" :max="100" :precision="2" :step="1" controls-position="right" placeholder="比例(%)" />
                </div>
              </el-form-item>
              <el-form-item label="VIP会员奖金">
                <div class="bonus-row">
                  <el-input-number v-model="form.bonus_price_vip" :min="0" :precision="2" :step="1" controls-position="right" placeholder="奖金(元)" />
                  <span class="bonus-sep">/</span>
                  <el-input-number v-model="form.bonus_rate_vip" :min="0" :max="100" :precision="2" :step="1" controls-position="right" placeholder="比例(%)" />
                </div>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>

        <!-- 右：状态 -->
        <el-col :span="12">
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="status-card-header">
                <span class="card-title">状态</span>
                <el-tag
                  v-if="isEdit"
                  :type="currentShelfStatus === 'on_shelf' ? 'success' : 'info'"
                  effect="plain"
                  size="small"
                >
                  {{ currentShelfStatus === 'on_shelf' ? '上架中' : '已下架' }}
                </el-tag>
              </div>
            </template>
            <el-form :model="form" label-width="120px" @submit.prevent>
              <el-form-item label="排序权重" prop="sort_order">
                <el-input-number v-model="form.sort_order" :min="0" :step="1" controls-position="right" />
                <div class="form-tip">数字越小越靠前，0 表示默认排序</div>
              </el-form-item>
              <el-form-item label="管理员备注" prop="admin_remark">
                <el-input
                  v-model="form.admin_remark"
                  type="textarea"
                  :rows="3"
                  placeholder="管理员备注"
                  maxlength="512"
                  show-word-limit
                />
              </el-form-item>
              <el-form-item v-if="isEdit && detailData" label="创建时间">
                <span class="readonly-text">{{ detailData.create_time || '-' }}</span>
              </el-form-item>
              <el-form-item v-if="isEdit && detailData" label="更新时间">
                <span class="readonly-text">{{ detailData.update_time || '-' }}</span>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>
      </el-row>

      <!-- 操作按钮 -->
      <div class="form-actions">
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
        <el-button @click="$router.push('/goods/list')">取消</el-button>
      </div>
    </div>

    <!-- 图片上传弹窗 -->
    <el-dialog v-model="uploadVisible" title="上传商品主图" width="520px">
      <ObsUploader v-model="uploadUrl" />
      <template #footer>
        <el-button @click="handleUploadCancel">取消</el-button>
        <el-button type="primary" :disabled="!uploadUrl" @click="handleUploadConfirm">确认使用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElPageHeader,
  ElCard,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElButton,
  ElIcon,
  ElImage,
  ElTag,
  ElDialog,
  ElRow,
  ElCol,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { goodsApi, type GoodsDetail } from '@/api/goods'
import ObsUploader from '@/components/ObsUploader.vue'

const route = useRoute()
const router = useRouter()

const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)

const isEdit = computed(() => !!route.params.goodsId)

interface GoodsFormState {
  goods_id: string
  source_channel: string
  goods_title: string
  goods_img: string
  sale_price: number
  original_price: number
  commission_rate: number
  bonus_price_normal: number
  bonus_rate_normal: number
  bonus_price_vip: number
  bonus_rate_vip: number
  category: string
  shop_name: string
  sort_order: number
  admin_remark: string
}

const form = reactive<GoodsFormState>({
  goods_id: '',
  source_channel: 'myq',
  goods_title: '',
  goods_img: '',
  sale_price: 0,
  original_price: 0,
  commission_rate: 0,
  bonus_price_normal: 0,
  bonus_rate_normal: 0,
  bonus_price_vip: 0,
  bonus_rate_vip: 0,
  category: '',
  shop_name: '',
  sort_order: 0,
  admin_remark: '',
})

/** 编辑模式下的详情原始数据（用于展示创建/更新时间） */
const detailData = ref<GoodsDetail | null>(null)
/** 编辑模式下的当前上下架状态（仅展示） */
const currentShelfStatus = ref<'on_shelf' | 'off_shelf'>('on_shelf')

const rules: FormRules = {
  goods_id: [
    { required: true, message: '请输入 CPS 商品ID', trigger: 'blur' },
    { max: 128, message: '最长 128 字符', trigger: 'blur' },
  ],
  source_channel: [{ required: true, message: '请选择来源渠道', trigger: 'change' }],
  goods_title: [{ max: 512, message: '标题最长 512 字符', trigger: 'blur' }],
  sale_price: [
    { required: true, message: '请输入销售价', trigger: 'blur' },
    { type: 'number', min: 0, message: '销售价不能为负', trigger: 'blur' },
  ],
  commission_rate: [
    { required: true, message: '请输入佣金比例', trigger: 'blur' },
    { type: 'number', min: 0, max: 100, message: '范围 0-100', trigger: 'blur' },
  ],
}

async function loadDetail() {
  if (!isEdit.value) return
  const goodsId = route.params.goodsId as string
  const sourceChannel = route.query.source_channel as string
  if (!goodsId || !sourceChannel) {
    ElMessage.error('缺少必要参数')
    router.push('/goods/list')
    return
  }
  loading.value = true
  try {
    const res = await goodsApi.getDetail(goodsId, sourceChannel)
    if (!res) {
      ElMessage.error('商品不存在')
      router.push('/goods/list')
      return
    }
    detailData.value = res
    Object.assign(form, {
      goods_id: res.goods_id,
      source_channel: res.source_channel,
      goods_title: res.goods_title,
      goods_img: res.goods_img,
      sale_price: Number(res.sale_price) || 0,
      original_price: Number(res.original_price) || 0,
      commission_rate: Number(res.commission_rate) || 0,
      bonus_price_normal: Number(res.bonus_price_normal) || 0,
      bonus_rate_normal: Number(res.bonus_rate_normal) || 0,
      bonus_price_vip: Number(res.bonus_price_vip) || 0,
      bonus_rate_vip: Number(res.bonus_rate_vip) || 0,
      category: res.category,
      shop_name: res.shop_name,
      sort_order: res.sort_order,
      admin_remark: res.admin_remark,
    })
    currentShelfStatus.value = res.shelf_status
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      await goodsApi.upsert({
        ...form,
        sale_price: String(form.sale_price ?? 0),
        original_price: String(form.original_price ?? 0),
        commission_rate: String(form.commission_rate ?? 0),
        bonus_price_normal: String(form.bonus_price_normal ?? 0),
        bonus_rate_normal: String(form.bonus_rate_normal ?? 0),
        bonus_price_vip: String(form.bonus_price_vip ?? 0),
        bonus_rate_vip: String(form.bonus_rate_vip ?? 0),
      })
      ElMessage.success(isEdit.value ? '商品更新成功' : '商品创建成功')
      router.push({
        path: `/goods/detail/${form.goods_id}`,
        query: { source_channel: form.source_channel },
      })
    } catch {
      // 拦截器已提示
    } finally {
      submitting.value = false
    }
  })
}

// ── 图片上传弹窗 ──────────────
const uploadVisible = ref(false)
const uploadUrl = ref('')

function openUpload() {
  uploadUrl.value = ''
  uploadVisible.value = true
}

function handleUploadCancel() {
  uploadVisible.value = false
  uploadUrl.value = ''
}

function handleUploadConfirm() {
  if (uploadUrl.value) {
    form.goods_img = uploadUrl.value
    ElMessage.success('图片已应用')
  }
  uploadVisible.value = false
  uploadUrl.value = ''
}

onMounted(() => {
  loadDetail()
})
</script>

<style scoped>
.goods-edit-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page-header {
  background: #fff;
  padding: 12px 20px;
  border-radius: 4px;
}

.page-title {
  font-size: 16px;
  font-weight: 500;
}

.section-card {
  margin-top: 0;
}

.card-title {
  font-weight: 500;
  font-size: 14px;
}

.status-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* ── 顶部：主图 + 基本信息 ── */
.edit-top-area {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.edit-image-wrap {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}

.edit-main-img {
  width: 200px;
  height: 200px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

.no-image {
  width: 200px;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #c0c4cc;
  border-radius: 6px;
  border: 1px solid #ebeef5;
  font-weight: 300;
}

.upload-btn {
  width: 200px;
}

.edit-basic-wrap {
  flex: 1;
  min-width: 0;
}

/* ── 价格区：奖金行 ── */
.bonus-row {
  display: flex;
  align-items: center;
  gap: 0;
}

.bonus-sep {
  color: #c0c4cc;
  margin: 0 8px;
}

/* ── 状态区 ── */
.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 4px;
  font-weight: 300;
}

.readonly-text {
  color: #606266;
  font-size: 14px;
}

/* ── 底部操作按钮 ── */
.form-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  padding: 16px 0;
}

:deep(.el-form-item__label) {
  font-weight: 300;
}
</style>
