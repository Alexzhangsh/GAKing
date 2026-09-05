<!-- @ai-generated -->
<!--
  商品详情页
  路由：/goods/detail/:goodsId?source_channel=xxx
  对接：GET /api/v1/admin/goods/{goodsId}?source_channel=xxx
-->
<template>
  <div class="goods-detail-page">
    <el-page-header @back="$router.push('/goods/list')" class="page-header">
      <template #content>
        <span class="page-title">商品详情</span>
      </template>
      <template #extra>
        <el-button type="primary" v-permission="'goods:manage'" @click="handleEdit">
          <el-icon><Edit /></el-icon>编辑商品
        </el-button>
      </template>
    </el-page-header>

    <div v-loading="loading">
      <template v-if="data">
        <!-- 顶部：主图 + 基本信息（并排） -->
        <el-card shadow="never" class="info-card">
          <div class="goods-top-area">
            <div class="goods-image-wrap">
              <el-image
                v-if="data.goods_img"
                :src="data.goods_img"
                :preview-src-list="[data.goods_img]"
                preview-teleported
                fit="contain"
                class="goods-main-img"
              />
              <div v-else class="no-image">暂无主图</div>
            </div>
            <div class="goods-info-wrap">
              <h3 class="goods-title">{{ data.goods_title || '(无标题)' }}</h3>
              <div class="title-meta">
                <el-tag size="small" :type="channelTagType(data.source_channel)" effect="plain">
                  {{ channelLabel(data.source_channel) }}
                </el-tag>
                <StatusTag :status="data.shelf_status" :map="shelfStatusMap" />
                <span class="goods-id">商品ID：{{ data.goods_id }}</span>
              </div>
              <el-descriptions :column="2" border size="small" class="basic-desc">
                <el-descriptions-item label="来源渠道">{{ channelLabel(data.source_channel) }}（{{ data.source_channel }}）</el-descriptions-item>
                <el-descriptions-item label="商品类目">{{ data.category || '-' }}</el-descriptions-item>
                <el-descriptions-item label="店铺名称">{{ data.shop_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="商品ID">{{ data.goods_id }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </el-card>

        <!-- 底部：价格 + 状态（两栏并排） -->
        <el-row :gutter="12">
          <el-col :span="12">
            <el-card shadow="never" class="info-card">
              <template #header><span class="card-title">价格</span></template>
              <el-descriptions :column="1" border size="small" class="price-desc">
                <el-descriptions-item label="商品原价">
                  <span :class="{ 'price-empty': !data.original_price || data.original_price === '0.00' }">
                    ¥{{ data.original_price || '0.00' }}
                  </span>
                </el-descriptions-item>
                <el-descriptions-item label="销售价"><span class="price-sale">¥{{ data.sale_price }}</span></el-descriptions-item>
                <el-descriptions-item label="佣金比例">{{ data.commission_rate }}%</el-descriptions-item>
                <el-descriptions-item label="普通会员奖金">
                  <span class="bonus-price">¥{{ data.bonus_price_normal || '0.00' }}</span>
                  <span class="bonus-sep">/</span>
                  <span class="bonus-rate">{{ data.bonus_rate_normal || '0.00' }}%</span>
                </el-descriptions-item>
                <el-descriptions-item label="VIP会员奖金">
                  <span class="bonus-price">¥{{ data.bonus_price_vip || '0.00' }}</span>
                  <span class="bonus-sep">/</span>
                  <span class="bonus-rate">{{ data.bonus_rate_vip || '0.00' }}%</span>
                </el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" class="info-card">
              <template #header><span class="card-title">状态</span></template>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="上下架状态">
                  <StatusTag :status="data.shelf_status" :map="shelfStatusMap" />
                </el-descriptions-item>
                <el-descriptions-item label="排序权重">{{ data.sort_order }}</el-descriptions-item>
                <el-descriptions-item label="最后操作管理员">{{ data.last_admin_id || '-' }}</el-descriptions-item>
                <el-descriptions-item label="管理员备注">{{ data.admin_remark || '-' }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ data.create_time || '-' }}</el-descriptions-item>
                <el-descriptions-item label="更新时间">{{ data.update_time || '-' }}</el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-col>
        </el-row>
      </template>

      <el-empty v-else-if="!loading" description="商品不存在或已被删除" />
    </div>
  </div>
</template>

<script setup lang="ts">
// @ai-generated
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElPageHeader,
  ElCard,
  ElButton,
  ElIcon,
  ElImage,
  ElTag,
  ElDescriptions,
  ElDescriptionsItem,
  ElEmpty,
} from 'element-plus'
import { Edit } from '@element-plus/icons-vue'
import StatusTag, { type StatusMap } from '@/components/StatusTag.vue'
import { goodsApi, type GoodsDetail } from '@/api/goods'

const route = useRoute()
const router = useRouter()

const data = ref<GoodsDetail | null>(null)
const loading = ref(false)

const shelfStatusMap: StatusMap = {
  on_shelf: { text: '上架', type: 'success' },
  off_shelf: { text: '下架', type: 'info' },
}

function channelLabel(code: string): string {
  const map: Record<string, string> = { myq: '喵有券', orderx: '订单侠', dta: '大淘客' }
  return map[code] || code
}

function channelTagType(code: string): 'primary' | 'success' | 'warning' {
  const map: Record<string, 'primary' | 'success' | 'warning'> = {
    myq: 'primary',
    orderx: 'success',
    dta: 'warning',
  }
  return map[code] || 'primary'
}

async function loadData() {
  const goodsId = route.params.goodsId as string
  const sourceChannel = route.query.source_channel as string
  if (!goodsId || !sourceChannel) {
    ElEmpty && void 0
    return
  }
  loading.value = true
  try {
    const res = await goodsApi.getDetail(goodsId, sourceChannel)
    data.value = res
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function handleEdit() {
  if (!data.value) return
  router.push({
    path: `/goods/edit/${encodeURIComponent(data.value.goods_id)}`,
    query: { source_channel: data.value.source_channel },
  })
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.goods-detail-page {
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

.info-card {
  margin-top: 12px;
}

.card-title {
  font-weight: 500;
  font-size: 14px;
}

.goods-top-area {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.goods-image-wrap {
  flex-shrink: 0;
}

.goods-main-img {
  width: 200px;
  height: 200px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

.goods-info-wrap {
  flex: 1;
  min-width: 0;
}

.goods-title {
  margin: 0 0 12px;
  font-size: 18px;
  color: #303133;
  line-height: 1.4;
}

.basic-desc {
  margin-top: 16px;
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

.title-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.goods-id {
  font-size: 13px;
  color: #909399;
  font-weight: 300;
}

.price-sale {
  color: #f56c6c;
  font-weight: 600;
  font-size: 15px;
}

.price-empty {
  color: #c0c4cc;
}

.bonus-price {
  color: #e6a23c;
  font-weight: 500;
}

.bonus-sep {
  color: #c0c4cc;
  margin: 0 6px;
}

.bonus-rate {
  color: #67c23a;
}

:deep(.el-descriptions__label) {
  width: 120px;
  font-weight: 300;
}

:deep(.price-desc .el-descriptions__label) {
  width: 130px;
}
</style>
