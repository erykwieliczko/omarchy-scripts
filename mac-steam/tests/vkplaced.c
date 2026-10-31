// A placed mapping of a reused BO must preserve the following reservation.
#define _GNU_SOURCE
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>

#define CHECK(call) do { VkResult r = (call); if (r) { printf("%s: %d\n", #call, r); return 1; } } while (0)

int main(void) {
    VkApplicationInfo app = {.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion=VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici = {.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo=&app};
    VkInstance inst; CHECK(vkCreateInstance(&ici, NULL, &inst));
    uint32_t n=1; VkPhysicalDevice pd; CHECK(vkEnumeratePhysicalDevices(inst, &n, &pd));
    VkPhysicalDeviceMapMemoryPlacedFeaturesEXT placed = {
        .sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MAP_MEMORY_PLACED_FEATURES_EXT};
    VkPhysicalDeviceFeatures2 features = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext=&placed};
    vkGetPhysicalDeviceFeatures2(pd, &features);
    if (!placed.memoryMapPlaced) { puts("SKIP: placed mapping unavailable"); return 77; }
    placed.memoryMapRangePlaced=VK_FALSE; placed.memoryUnmapReserve=VK_FALSE;
    const char *exts[] = {VK_EXT_MAP_MEMORY_PLACED_EXTENSION_NAME, VK_KHR_MAP_MEMORY_2_EXTENSION_NAME};
    float priority=1;
    VkDeviceQueueCreateInfo q = {.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueCount=1, .pQueuePriorities=&priority};
    VkDeviceCreateInfo dci = {.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext=&placed,
        .queueCreateInfoCount=1, .pQueueCreateInfos=&q, .enabledExtensionCount=2, .ppEnabledExtensionNames=exts};
    VkDevice dev; CHECK(vkCreateDevice(pd, &dci, NULL, &dev));
    PFN_vkMapMemory2KHR map2 = (void *)vkGetDeviceProcAddr(dev, "vkMapMemory2KHR");
    const size_t large=7*1024*1024, small=5*1024*1024, guard=3*1024*1024;
    VkMemoryAllocateInfo ai = {.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .allocationSize=large, .memoryTypeIndex=0};
    VkDeviceMemory mem; CHECK(vkAllocateMemory(dev, &ai, NULL, &mem));
    void *ptr; CHECK(vkMapMemory(dev, mem, 0, VK_WHOLE_SIZE, 0, &ptr));
    memset(ptr, 0x17, large);
    vkUnmapMemory(dev, mem); vkFreeMemory(dev, mem, NULL);
    ai.allocationSize=small; CHECK(vkAllocateMemory(dev, &ai, NULL, &mem));
    unsigned char *area=mmap(NULL, small+guard, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if (area==MAP_FAILED) return 2;
    memset(area+small, 0x5a, guard);
    VkMemoryMapPlacedInfoEXT pi = {.sType=VK_STRUCTURE_TYPE_MEMORY_MAP_PLACED_INFO_EXT, .pPlacedAddress=area};
    VkMemoryMapInfoKHR mi = {.sType=VK_STRUCTURE_TYPE_MEMORY_MAP_INFO_KHR, .pNext=&pi,
        .flags=VK_MEMORY_MAP_PLACED_BIT_EXT, .memory=mem, .size=VK_WHOLE_SIZE};
    CHECK(map2(dev, &mi, &ptr));
    size_t changed=0;
    for (size_t i=0; i<guard; ++i) changed += area[small+i]!=0x5a;
    printf("placed=%s guard_changed=%zu\n", ptr==area?"correct":"WRONG", changed);
    vkUnmapMemory(dev, mem); vkFreeMemory(dev, mem, NULL);
    munmap(area, small+guard);
    vkDestroyDevice(dev, NULL); vkDestroyInstance(inst, NULL);
    return changed || ptr!=area;
}
