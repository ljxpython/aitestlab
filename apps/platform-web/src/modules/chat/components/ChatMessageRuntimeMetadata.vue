<script setup lang="ts">
import { useMessageMetadata, type AnyStream } from '@langchain/vue'

const props = defineProps<{
  stream: AnyStream
  messageId: string
}>()

const metadata = useMessageMetadata(props.stream, () => props.messageId)
</script>

<template>
  <slot :metadata="metadata" />
</template>
