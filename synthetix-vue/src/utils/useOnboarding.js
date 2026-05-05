import { ref, onMounted } from 'vue'

const TOUR_KEY = 'synthetix_tour_done'

export function useOnboarding(steps) {
  const active = ref(false)
  const currentStep = ref(0)

  const startTour = () => {
    if (localStorage.getItem(TOUR_KEY)) return
    active.value = true
    currentStep.value = 0
  }

  const nextStep = () => {
    if (currentStep.value < steps.length - 1) {
      currentStep.value++
    } else {
      dismiss()
    }
  }

  const prevStep = () => {
    if (currentStep.value > 0) currentStep.value--
  }

  const dismiss = () => {
    active.value = false
    localStorage.setItem(TOUR_KEY, '1')
  }

  const resetTour = () => {
    localStorage.removeItem(TOUR_KEY)
    active.value = true
    currentStep.value = 0
  }

  return { active, currentStep, startTour, nextStep, prevStep, dismiss, resetTour }
}
