import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatComposer from './ChatComposer.vue'

type ComposerProps = InstanceType<typeof ChatComposer>['$props']

function mountComposer(overrides: Partial<ComposerProps> = {}) {
  return mount(ChatComposer, {
    props: {
      modelValue: '',
      attachments: [],
      isRunning: false,
      hasBlockingInterrupt: false,
      canStartThread: true,
      showContinueAction: false,
      canSendFreshMessage: false,
      cancelling: false,
      sendButtonLabel: '发送消息',
      lastEventAt: '',
      compact: true,
      'onUpdate:modelValue': () => undefined,
      ...overrides
    } as ComposerProps,
    global: {
      stubs: {
        ChatInterruptPanel: true,
        ChatAttachmentPreview: true
      }
    }
  })
}

describe('ChatComposer', () => {
  it('does not render legacy resize or expand controls in compact mode', () => {
    const wrapper = mountComposer()

    expect(wrapper.find('button[aria-label="拖拽调整输入框高度"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('展开输入框')
    expect(wrapper.text()).not.toContain('支持 JPEG')
  })

  it('preserves the draft while the primary action switches from send to cancel', async () => {
    const wrapper = mountComposer({
      modelValue: '尚未发送的草稿',
      canSendFreshMessage: true
    })

    expect(wrapper.get('textarea').element.value).toBe('尚未发送的草稿')
    expect(wrapper.text()).toContain('发送消息')

    await wrapper.setProps({ isRunning: true })
    expect(wrapper.get('textarea').element.value).toBe('尚未发送的草稿')
    expect(wrapper.text()).toContain('停止生成')

    await wrapper.findAll('button').at(-1)?.trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })
})
